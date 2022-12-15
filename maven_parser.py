import subprocess
from pathlib import Path
import shlex
import re
import sys


def auto_str(cls):
    def __str__(self):
        return "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % item for item in vars(self).items()))

    cls.__str__ = __str__
    return cls


@auto_str
class TestVerdict:
    SUCCESS = "success"
    FAILURE = "failure"
    COMPILE_ERR = "compile_error"

    def __init__(self, status, error_lines):
        self.status = status
        self.error_line = error_lines


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

    matches = re.compile(f"^\[ERROR\] {str(test_path)}:\[(\d+),\d+\].*$", re.MULTILINE).findall(log)
    if len(matches) == 0:
        print(f"{log}\nCannot match compile error location in the above log. Test: {test_path}")
        sys.exit()

    error_lines = set([int(m) for m in matches])
    return TestVerdict(TestVerdict.COMPILE_ERR, error_lines)


def parse_test_failure(log, test_class, test_method):
    matches = re.compile(f"^\[ERROR\]\s*{test_class}\.{test_method}:(\d+).*$", re.MULTILINE).findall(log)
    if len(matches) == 0:
        print(f"{log}\nCannot match test failure location in the above log. Test: {test_class}.{test_method}")
        sys.exit()

    error_lines = set([int(m) for m in matches])
    return TestVerdict(TestVerdict.FAILURE, error_lines)


def compile_and_run_test(project_path, test_rel_path, test_method):
    test_path = project_path / test_rel_path
    test_class = test_path.stem
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
    result = subprocess.run(shlex.split(" ".join(cmd)), capture_output=True, text=True)
    if result.returncode == 0:
        return TestVerdict(TestVerdict.SUCCESS, None)

    compile_error = parse_compile_error(result.stdout, test_path)
    if compile_error is not None:
        return compile_error

    return parse_test_failure(result.stdout, test_class, test_method)


project_p = Path("/home/ahmad/workspace/tc-repair/api_cache/clones/apache@shardingsphere")
test_f = Path(
    "agent/core/src/test/java/org/apache/shardingsphere/agent/core/bytebuddy/transformer/ShardingSphereTransformerTest.java"
)
result = compile_and_run_test(project_p, test_f, "assertInstanceMethodInRepeatedAdvice")
print(result)
