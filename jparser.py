# TODO After all data sources are mined, for each test repair, we should find the intersection between test coverage and SUT changes in the release.
# Finally, we need to extract the changed Git Hunks of the covered changes to complete the initial dataset.
from main import jparser_path
import subprocess
import pandas as pd


def find_test_classes(source_code_path):
    tests_output_file = source_code_path.parent / "tests.csv"
    if not tests_output_file.exists():
        print(f"Finding test classes for {source_code_path.parent.name}")
        cmd = f"java -jar {jparser_path} testClasses -s {source_code_path} -cl 10 -o {tests_output_file}"
        cmd_out = subprocess.run(cmd, shell=True, capture_output=True)
        if cmd_out.returncode != 0:
            print(f"Error in finding test cases:\n{cmd_out.stderr}")

    tests = pd.read_csv(tests_output_file)
    return tests


def extract_test_methods(test_file):
    methods_path = test_file.parent / "methods"
    if methods_path.exists() and any(methods_path.iterdir()):
        return

    cmd = (
        f"java -jar {jparser_path} testMethods -s {test_file} -cl 10 -o {methods_path}"
    )
    cmd_out = subprocess.run(cmd, shell=True, capture_output=True)
    if cmd_out.returncode != 0:
        print(f"Error in method extraction:\n{cmd_out.stderr}")


def create_call_graphs(output_path, release_tag):
    release_code_path = output_path / "releases" / release_tag / "code"
    cmd = f"java -jar {jparser_path} callGraphs -s {release_code_path} -cl 10 -o {output_path} -t {release_tag}"
    cmd_out = subprocess.run(cmd, shell=True, capture_output=True)
    if cmd_out.returncode != 0:
        print(f"Error in method extraction:\n{cmd_out.stderr.decode('utf-8')}")