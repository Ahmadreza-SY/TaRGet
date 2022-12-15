import argparse
from config import Config
from services import Service


def analyze_github_tags(args):
    Service.analyze_repair_commits()


def create_test_repair_dataset(args):
    Service.create_dataset()


def add_common_arguments(parser):
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


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    gh_tags_parser = subparsers.add_parser(
        "gh_tags",
        help="Analyzes all tags in the given GitHub repository and finds test case repairs.",
    )
    gh_tags_parser.set_defaults(func=analyze_github_tags)
    add_common_arguments(gh_tags_parser)

    dataset_parser = subparsers.add_parser(
        "dataset",
        help="Creates a test case repair dataset that includes test code before and after repair plus SUT changes covered by tests cases across all tags",
    )
    dataset_parser.set_defaults(func=create_test_repair_dataset)
    add_common_arguments(dataset_parser)

    args = parser.parse_args()
    Config.set("repo", args.repository)
    Config.set("output_path", args.output_path)
    args.func(args)


if __name__ == "__main__":
    main()
