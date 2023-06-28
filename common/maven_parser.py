import subprocess
from subprocess import TimeoutExpired
import shlex
import re
from config import Config
import os
from common_utils import auto_str, find_parent_pom
from java_version_detector import JavaVersionDetector
from pathlib import Path


@auto_str
class TestVerdict:
    # Valid results
    SUCCESS = "success"
    FAILURE = "failure"
    COMPILE_ERR = "compile_error"
    # Invalid results
    TIMEOUT = "timeout"
    TEST_NOT_EXECUTED = "test_not_executed"
    UNRELATED_COMPILE_ERR = "unrelated_compile_error"
    EXPECTED_EXCEPTION_FAILURE = "expected_exception_failure"
    TEST_MATCH_FAILURE = "test_match_failure"
    UNRELATED_FAILURE = "unrelated_failure"
    DEPENDENCY_ERROR = "dependency_error"
    POM_NOT_FOUND = "pom_not_found"
    UNKNOWN = "unknown"

    def __init__(self, status, error_lines):
        self.status = status
        self.error_lines = error_lines

    def is_valid(self):
        return self.status in [TestVerdict.SUCCESS, TestVerdict.FAILURE, TestVerdict.COMPILE_ERR]

    def is_broken(self):
        return self.is_valid() and self.status != TestVerdict.SUCCESS

    def succeeded(self):
        return self.status == TestVerdict.SUCCESS

    def to_dict(self):
        return {
            "status": self.status,
            "error_lines": sorted(list(self.error_lines)) if self.error_lines is not None else None,
        }


def parse_compile_error(log, test_rel_path):
    if "COMPILATION ERROR" not in log and "Compilation failure:" not in log:
        return None

    matches = re.compile(f"^\[ERROR\]\s*/.+/{test_rel_path}:\[(\d+),\d+\].*$", re.MULTILINE).findall(log)
    if len(matches) == 0:
        return None

    error_lines = set([int(m) for m in matches])
    return TestVerdict(TestVerdict.COMPILE_ERR, error_lines)


def parse_test_failure(log, test_class, test_method):
    regexes = [
        f"^\[ERROR\]\s*{test_class}\.{test_method}:(\d+).*$",
        f"^\s*at .+{test_class}.{test_method}\({test_class}\.java:(\d+)\).*$",
    ]
    matches = []
    for regex in regexes:
        matches = re.compile(regex, re.MULTILINE).findall(log)
        if len(matches) > 0:
            break

    if len(matches) == 0:
        regex = r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+).*Time elapsed.*"
        match = re.compile(regex).search(log)
        if match:
            failures, errors = int(match.group(2)), int(match.group(3))
            if failures > 0 or errors > 0:
                return TestVerdict(TestVerdict.FAILURE, set())
            runs, skips = int(match.group(1)), int(match.group(4))
            if runs == 0 or skips > 0:
                return TestVerdict(TestVerdict.TEST_NOT_EXECUTED, None)
        return None

    error_lines = set([int(m) for m in matches])
    return TestVerdict(TestVerdict.FAILURE, error_lines)


def parse_invalid_execution(log):
    if "COMPILATION ERROR" in log or "Compilation failure:" in log:
        return TestVerdict(TestVerdict.UNRELATED_COMPILE_ERR, None)
    if "java.lang.AssertionError: Expected exception:" in log:
        return TestVerdict(TestVerdict.EXPECTED_EXCEPTION_FAILURE, None)
    if "java.lang.Exception: No tests found matching Method" in log:
        return TestVerdict(TestVerdict.TEST_MATCH_FAILURE, None)
    if "<<< ERROR!" in log:
        return TestVerdict(TestVerdict.UNRELATED_FAILURE, None)
    if "Could not resolve dependencies" in log or "Non-resolvable parent POM" in log:
        return TestVerdict(TestVerdict.DEPENDENCY_ERROR, None)

    return TestVerdict(TestVerdict.UNKNOWN, None)


def parse_successful_execution(log):
    matches = re.compile(
        r"^.*Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+).*Time elapsed.*$", re.MULTILINE
    ).findall(log)
    for match in matches:
        runs, failures, errors, skips = (int(n) for n in match)
        if runs == 1 and failures == 0 and errors == 0 and skips == 0:
            return TestVerdict(TestVerdict.SUCCESS, None)
    return TestVerdict(TestVerdict.TEST_NOT_EXECUTED, None)


def run_cmd(cmd, java_home=None):
    my_env = os.environ.copy()
    if java_home is not None:
        my_env["JAVA_HOME"] = java_home

    retries = 0
    while True:
        proc = subprocess.Popen(shlex.split(" ".join(cmd)), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=my_env)
        try:
            stdout, stderr = proc.communicate(timeout=15 * 60)
            return proc.returncode, stdout.decode("utf-8")
        except TimeoutExpired as e:
            proc.kill()
            if retries < 1:
                retries += 1
                continue
            return 124, e.stdout.decode("utf-8")


def remove_unnecessary_plugins(pom_path):
    if not pom_path.exists():
        return
    pom = pom_path.read_text()
    plugins = [
        (r"org\.codehaus\.mojo", r"findbugs-maven-plugin"),
        (r"pl\.project13\.maven", r"git-commit-id-plugin"),
        (r"io\.github\.git-commit-id", r"git-commit-id-maven-plugin"),
        (r"org\.apache\.maven\.plugins", r"maven-checkstyle-plugin"),
    ]
    new_pom = pom
    for groupId, artifactId in plugins:
        regex = r"<plugin>\s*<groupId>{}</groupId>\s*<artifactId>{}</artifactId>.*?</plugin>".format(groupId, artifactId)
        match = re.compile(regex, re.DOTALL).search(new_pom)
        if match:
            new_pom = new_pom.replace(match.group(), "")
    if new_pom != pom:
        pom_path.write_text(new_pom)


MVN_SKIPS = [
    "-Djacoco.skip",
    "-Dcheckstyle.skip",
    "-Dspotless.apply.skip",
    "-Drat.skip",
    "-Denforcer.skip",
    "-Danimal.sniffer.skip",
    "-Dmaven.javadoc.skip",
    "-Dmaven.gitcommitid.skip",
    "-Dfindbugs.skip",
    "-Dwarbucks.skip",
    "-Dmodernizer.skip",
    "-Dimpsort.skip",
    "-Dpmd.skip",
    "-Dxjc.skip",
    "-Dair.check.skip-all",
    "-Dlicense.skip",
    "-Dfindbugs.skip",
    "-Denforcer.skip",
    "-Dremoteresources.skip",
]


def compile_and_run_test(project_path, test_rel_path, test_method, log_path, save_logs=True, mvn_args=[]):
    log_file = log_path / "test.log"
    test_path = project_path / test_rel_path
    if not test_path.exists():
        raise FileNotFoundError(f"Test file does not exist: {test_path}")
    test_class = test_path.stem
    if log_file.exists():
        log = log_file.read_text()
        returncode = int(log.splitlines()[0])
    else:
        pom_path = find_parent_pom(test_path)
        if pom_path is None:
            return TestVerdict(TestVerdict.POM_NOT_FOUND, None)
        remove_unnecessary_plugins(project_path / "pom.xml")
        remove_unnecessary_plugins(pom_path)
        cmd = [
            "mvn",
            "test",
            f"-pl {str(pom_path.relative_to(project_path))}",
            "--also-make",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            "-DfailIfNoTests=false",
            f'-Dtest="{test_class}#{test_method}"',
            "--batch-mode",
        ]
        if len(mvn_args) > 0:
            cmd.extend(mvn_args)
        cmd.extend(MVN_SKIPS)
        m2_path = Config.get("m2_path")
        if m2_path is not None:
            cmd.append(f"-Dmaven.repo.local={m2_path}")
        original_cwd = os.getcwd()
        os.chdir(str(project_path.absolute()))
        jvd = JavaVersionDetector(Path("pom.xml"))
        java_home = jvd.get_java_home()
        returncode, log = run_cmd(cmd, java_home)
        os.chdir(original_cwd)
        if save_logs:
            log_path.mkdir(parents=True, exist_ok=True)
            log_file.write_text("\n".join([str(returncode), " ".join(cmd), f"JAVA_HOME={java_home}", log]))

    if returncode == 0:
        return parse_successful_execution(log)

    if returncode == 124:
        return TestVerdict(TestVerdict.TIMEOUT, None)

    compile_error = parse_compile_error(log, test_rel_path)
    if compile_error is not None:
        return compile_error

    failure = parse_test_failure(log, test_class, test_method)
    if failure is not None:
        return failure

    return parse_invalid_execution(log)
