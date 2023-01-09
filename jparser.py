import subprocess
import sys
from config import Config


def run_command(cmd):
    cmd_out = subprocess.run(cmd, shell=True)
    if cmd_out.returncode != 0:
        print(f"Error in running command: {cmd}")
        sys.exit()


def compare_test_classes(output_path):
    cmd = f"java -jar {Config.get('jparser_path')} compare -o {output_path}"
    run_command(cmd)


def extract_covered_changes_info(output_path):
    cmd = f"java -jar {Config.get('jparser_path')} coverage -o {output_path}"
    run_command(cmd)
