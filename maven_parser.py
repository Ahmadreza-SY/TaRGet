import subprocess
from pathlib import Path
import shlex
import re
import sys
from utils import auto_str
from config import Config
import os


@auto_str
class TestVerdict:
    SUCCESS = "success"
    FAILURE = "failure"
    COMPILE_ERR = "compile_error"

    def __init__(self, status, error_lines):
        self.status = status
        self.error_lines = error_lines


def find_parent_pom(file_path):
    current_dir = file_path.parent
    while True:
        if (current_dir / "pom.xml").exists():
            return current_dir / "pom.xml"
        current_dir = current_dir.parent
        if current_dir == Path("/"):
            print(f"No pom.xml parent found for {file_path}")
            return None


def parse_compile_error(log, test_path):
    if "COMPILATION ERROR" not in log:
        return None

    matches = re.compile(f"^\[ERROR\]\s*{str(test_path.absolute())}:\[(\d+),\d+\].*$", re.MULTILINE).findall(log)
    if len(matches) == 0:
        print(f"Cannot match compile error location in the above log. Test: {test_path}")
        sys.exit()

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
        cmd = [
            "mvn",
            "test",
            f'-f {str(project_path / "pom.xml")}',
            f"-pl {str(pom_path.relative_to(project_path))}",
            "--also-make",
            "-Dsurefire.failIfNoSpecifiedTests=false",
            f'-Dtest="{test_class}#{test_method}"',
            "-Dcheckstyle.skip",
        ]
        java_home = Config.get("java_home")
        my_env = os.environ.copy()
        if java_home is not None:
            my_env["JAVA_HOME"] = java_home
        result = subprocess.run(shlex.split(" ".join(cmd)), capture_output=True, text=True, env=my_env)
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
    if failure == None:
        print(f"Cannot match test failure location in the above log. Test: {test_class}.{test_method} at {log_path}")
        sys.exit()
    return failure


def cleanup(project_path):
    if not list(project_path.glob("**/target")):
        return
    cmd = ["mvn", "clean", f'-f {str(project_path / "pom.xml")}']
    result = subprocess.run(shlex.split(" ".join(cmd)), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Failed cleaning mvn at {project_path}, CMD: {cmd}")
