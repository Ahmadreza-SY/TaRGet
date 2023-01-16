import subprocess
import sys
from config import Config


def run_command(cmd):
    cmd_out = subprocess.run(" ".join(cmd), shell=True)
    if cmd_out.returncode != 0:
        print(f"Error in running command: {cmd}")
        sys.exit()


def compare_test_classes(output_path):
    cmd = ["java", "-jar", Config.get("jparser_path"), "compare", "-o", str(output_path)]
    run_command(cmd)


def extract_covered_changes_info(output_path):
    cmd = ["java", "-jar", Config.get("jparser_path"), "coverage", "-o", str(output_path)]
    run_command(cmd)
