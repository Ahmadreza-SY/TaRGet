import subprocess
import pandas as pd
import sys
from config import Config


def run_command(cmd):
    cmd_out = subprocess.run(cmd, shell=True)
    if cmd_out.returncode != 0:
        print(f"Error in running command: {cmd}")
        sys.exit()


def find_test_classes(source_code_path):
    tests_output_file = source_code_path.parent / "tests.csv"
    if not tests_output_file.exists():
        print(f"Finding test classes for {source_code_path.parent.name}")
        cmd = f"java -jar {Config.get('jparser_path')} testClasses -s {source_code_path} -cl 10 -o {tests_output_file}"
        run_command(cmd)

    if tests_output_file.stat().st_size == 0:
        print(f"No test class found for {source_code_path.parent.name}")
        return pd.DataFrame()
    tests = pd.read_csv(tests_output_file)
    return tests


def extract_test_methods(test_file):
    methods_path = test_file.parent / "methods"
    if methods_path.exists() and any(methods_path.iterdir()):
        return

    cmd = f"java -jar {Config.get('jparser_path')} testMethods -s {test_file} -cl 10 -o {methods_path}"
    run_command(cmd)


def create_call_graphs(output_path, release_tag):
    release_code_path = output_path / "tags" / release_tag / "code"
    cmd = (
        f"java -jar {Config.get('jparser_path')} callGraphs -s {release_code_path} -cl 10 -o {output_path} -t {release_tag}"
    )
    run_command(cmd)


def detect_changed_methods(output_path):
    cmd = f"java -jar {Config.get('jparser_path')} methodChanges -o {output_path}"
    run_command(cmd)