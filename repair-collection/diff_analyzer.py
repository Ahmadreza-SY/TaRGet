import sys

sys.path.append("../common")
import git_api as gapi
from config import Config
import argparse
from pathlib import Path
import json
from tqdm import tqdm
import pandas as pd
import jparser


def categorize_repairs(args):
    dataset = json.loads((args.output_path / "dataset.json").read_text())
    repair_patches = {"id": [], "before_path": [], "after_path": []}
    for repair in tqdm(dataset, desc="Writing repair patch files"):
        repair_id = repair["ID"]
        path_id = repair_id.replace("/", ":")
        repair_patches_path = args.output_path / "repairPatches" / path_id
        repo_name = repair_id.split(":")[0]
        file_name = Path(repair["aPath"]).name

        after_content = gapi.get_file_version(repair["aCommit"], repair["aPath"], repo_name)
        after_file = repair_patches_path / "after" / file_name
        after_file.parent.mkdir(parents=True, exist_ok=True)
        after_file.write_text(after_content)

        a_source = repair["aSource"]["code"]
        b_source = repair["bSource"]["code"]
        before_content = after_content.replace(a_source, b_source)
        before_file = repair_patches_path / "before" / file_name
        before_file.parent.mkdir(parents=True, exist_ok=True)
        before_file.write_text(before_content)

        repair_patches["id"].append(repair_id)
        repair_patches["before_path"].append(before_file.relative_to(args.output_path))
        repair_patches["after_path"].append(after_file.relative_to(args.output_path))

    pd.DataFrame(repair_patches).to_csv(args.output_path / "repair_patches.csv", index=False)

    jparser.categorize_repair_diffs(args.output_path)


def main():
    parser = argparse.ArgumentParser(
        prog="Test Repair Categorizer",
        description="This script categorizes the change types of collected test repairs using the GumTree tool.",
    )
    parser.set_defaults(func=categorize_repairs)
    parser.add_argument(
        "-o",
        "--output-path",
        help="Path to the existing dataset",
        type=str,
        required=True,
    )

    args = parser.parse_args()
    args.output_path = Path(args.output_path)
    Config.set("output_path", args.output_path)
    args.func(args)


if __name__ == "__main__":
    main()
