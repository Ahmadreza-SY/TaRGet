import argparse
from config import Config
from services import Service


def analyze_github_releases(args):
    Config.set("gh_api_token", args.api_token)
    Service.analyze_release_and_repairs()


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

    gh_releases_parser = subparsers.add_parser(
        "gh_releases",
        help="Analyzes all releases in the given GitHub repository and finds test case repairs.",
    )
    gh_releases_parser.set_defaults(func=analyze_github_releases)
    add_common_arguments(gh_releases_parser)
    gh_releases_parser.add_argument(
        "-t",
        "--api-token",
        help="A GitHub API token for fetching releases, diff, and source code",
        type=str,
        required=True,
    )

    dataset_parser = subparsers.add_parser(
        "dataset",
        help="Creates a test case repair dataset that includes test code before and after repair plus SUT changes covered by tests cases across all releases",
    )
    dataset_parser.set_defaults(func=create_test_repair_dataset)
    add_common_arguments(dataset_parser)

    args = parser.parse_args()
    Config.set("repo", args.repository)
    Config.set("output_path", args.output_path)
    args.func(args)


if __name__ == "__main__":
    main()
