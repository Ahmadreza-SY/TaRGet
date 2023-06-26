import sys

sys.path.append("../common")
from config import Config
import argparse
from data_collector import DataCollector


def collect_test_repairs(args):
    collector = DataCollector(args.repository, args.output_path)
    collector.collect_test_repairs()


def main():
    parser = argparse.ArgumentParser(
        prog="Test Repair Data Collector",
        description="Collects test repair data by anaylzing git commits for the given GitHub repo",
    )
    parser.set_defaults(func=collect_test_repairs)
    parser.add_argument(
        "-r",
        "--repository",
        help="The login and name of the repo seperated by / (e.g., dbeaver/dbeaver)",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output-path",
        help="The directory to save resulting information and data",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-j",
        "--java-homes",
        help="Path to a json file that contains java homes for all java versions.",
        type=str,
        required=False,
        default=None,
    )
    parser.add_argument(
        "-m2",
        "--m2-path",
        help="Custom path for maven local repository",
        type=str,
        required=False,
        default=None,
    )

    args = parser.parse_args()
    Config.set("repo", args.repository)
    Config.set("output_path", args.output_path)
    Config.set("java_homes_path", args.java_homes)
    Config.set("m2_path", args.m2_path)
    args.func(args)


if __name__ == "__main__":
    main()
