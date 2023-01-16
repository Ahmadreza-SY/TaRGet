import subprocess
from pathlib import Path
import shlex
import re
from utils import auto_str
from config import Config
import os


@auto_str
class TestVerdict:
    # Valid results
    SUCCESS = "success"
    FAILURE = "failure"
    COMPILE_ERR = "compile_error"
    # Invalid results
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


def find_parent_pom(file_path):
    current_dir = file_path.parent
    while True:
        if (current_dir / "pom.xml").exists():
            return current_dir / "pom.xml"
        current_dir = current_dir.parent
        if current_dir == current_dir.parent:
            return None


def parse_compile_error(log, test_path):
    if "COMPILATION ERROR" not in log:
        return None

    matches = re.compile(f"^\[ERROR\]\s*{str(test_path.absolute())}:\[(\d+),\d+\].*$", re.MULTILINE).findall(log)
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
        return None

    error_lines = set([int(m) for m in matches])
    return TestVerdict(TestVerdict.FAILURE, error_lines)


def parse_invalid_execution(log):
    if "COMPILATION ERROR" in log:
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


def run_cmd(cmd):
    java_home = Config.get("java_home")
    my_env = os.environ.copy()
    if java_home is not None:
        my_env["JAVA_HOME"] = java_home
    return subprocess.run(shlex.split(" ".join(cmd)), capture_output=True, text=True, env=my_env)


def compile_and_run_test(project_path, test_rel_path, test_method, log_path):
    log_file = log_path / "test.log"
    rc_file = log_path / "returncode"
    test_path = project_path / test_rel_path
    test_class = test_path.stem
    if log_file.exists():
        returncode = int(rc_file.read_text())
        log = log_file.read_text()
    else:
        pom_path = find_parent_pom(test_path)
        if pom_path is None:
            return TestVerdict(TestVerdict.POM_NOT_FOUND, None)
        cmd = [
            "mvn",
            "clean",
            "test",
            f'-f {str(project_path / "pom.xml")}',
            f"-pl {str(pom_path.relative_to(project_path))}",
            "--also-make",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            f'-Dtest="{test_class}#{test_method}"',
            "-Dcheckstyle.skip",
            "--batch-mode",
        ]
        result = run_cmd(cmd)
        returncode = result.returncode
        log = result.stdout
        log_path.mkdir(parents=True, exist_ok=True)
        rc_file.write_text(str(returncode))
        log_file.write_text(log)
        cmd_file = log_path / "command"
        cmd_file.write_text(" ".join(cmd))

    if returncode == 0:
        return TestVerdict(TestVerdict.SUCCESS, None)

    compile_error = parse_compile_error(log, test_path)
    if compile_error is not None:
        return compile_error

    failure = parse_test_failure(log, test_class, test_method)
    if failure is not None:
        return failure

    return parse_invalid_execution(log)
