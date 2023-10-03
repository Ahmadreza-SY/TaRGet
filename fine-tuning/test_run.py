import sys

sys.path.append("../common")
import argparse
import logging
import json
from tqdm import tqdm
from pathlib import Path
import pandas as pd
from common_utils import decompose_full_method_name
from config import Config
import maven_parser as mvnp
import git_api as gapi
from encoders.preprocessing.editSequence import apply_edit_sequence

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%m-%d-%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("MAIN")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-o",
        "--output-path",
        required=True,
        type=str,
        help="The directory where predictions are saved and execution results will be saved.",
    )
    parser.add_argument(
        "-r",
        "--repo-path",
        required=False,
        type=str,
        help="The directory where tests will be executed.",
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
        "-i",
        "--test-index",
        help="The index of the row to execute from the test split. If not provided, all rows from test split will be executed",
        type=int,
        required=True,
    )
    parser.add_argument(
        "-m2",
        "--m2-path",
        help="Custom path for maven local repository",
        type=str,
        required=False,
        default=None,
    )
    parser.add_argument("-do", "--discard-logs", dest="discard_logs", action="store_true")
    parser.set_defaults(discard_logs=False)
    # TODO Remove this and the related code because we are applying edit seq in prediction phase
    parser.add_argument("-eds", "--edit_sequence", dest="edit_sequence", action="store_true")
    parser.set_defaults(edit_sequence=False)
    args = parser.parse_args()
    args.output_path = Path(args.output_path)
    Config.set("output_path", args.output_path)
    Config.set("repo_path", args.repo_path)
    Config.set("java_homes_path", args.java_homes)
    Config.set("m2_path", args.m2_path)

    pred_file = args.output_path / "test_predictions.json"
    pred_df = pd.read_json(pred_file)
    test_rows = json.loads((args.output_path / "splits" / "test.json").read_text())
    selected_test = test_rows[args.test_index]
    pred_df = pred_df[pred_df["id"] == selected_test["ID"]].reset_index(drop=True)

    logger.info(f"Starting to execute {len(pred_df)} candidate repair patches - test ID {selected_test['ID']}")
    results = apply_and_run_preds(pred_df, selected_test, args)

    verdict_df, _ = analyze_verdicts(results)
    if len(verdict_df) > 0:
        verdicts_file = args.output_path / "test_verdicts" / f"{args.test_index}.json"
        verdicts_file.parent.mkdir(exist_ok=True, parents=True)
        verdict_df.to_json(verdicts_file, orient="records", indent=2)
        logger.info(f"Execution finished!")


def analyze_verdicts(verdicts):
    vs_df = pd.DataFrame({"verdict": [r[0]["status"] for r in verdicts]})
    logger.info("Verdict stats:")
    for v, cnt in vs_df["verdict"].value_counts().items():
        print(f"    {v} -> {round(100*cnt/len(vs_df), 1)}% ({cnt})")

    verdict_df = pd.DataFrame(
        {"verdict": [r[0] for r in verdicts], "id": [r[1] for r in verdicts], "rank": [r[2] for r in verdicts]}
    )
    verdict_df["success"] = verdict_df["verdict"].apply(lambda v: 1 if v["status"] == mvnp.TestVerdict.SUCCESS else 0)
    success_cnt = verdict_df.groupby("id").filter(lambda g: g["success"].sum() >= 1)["id"].nunique()
    plausible_rate = round(100 * success_cnt / verdict_df["id"].nunique(), 1)
    logger.info(f"Plausible Rate: {plausible_rate} %")

    return verdict_df, plausible_rate


def apply_patch(patch, test, test_file, edit_sequence=False):
    with open(test_file, "r") as orig_file:
        original_contents = orig_file.read()
    with open(test_file, "r") as orig_file:
        contents = orig_file.read()

    if edit_sequence:
        orig_test = test["bSource"]["code"]
        updated_test = apply_edit_sequence(orig_test, patch)
        if updated_test is None:
            return None

        contents = contents.replace(test["aSource"]["code"], "\n".join(updated_test))

    else:
        if "targetChanges" in test["hunk"] and len(test["hunk"]["targetChanges"]) > 0:
            contents = contents.split("\n")
            target_line = test["hunk"]["targetChanges"][0]["lineNo"] - 1
            for tc in test["hunk"]["targetChanges"][::-1]:
                del contents[tc["lineNo"] - 1]
            contents.insert(target_line, patch)
            contents = "\n".join(contents)
        else:
            test_method = test["bSource"]["code"].split("\n")
            start_line = test["bSource"]["startLine"]
            target_line = test["hunk"]["sourceChanges"][0]["lineNo"] - start_line
            for tc in test["hunk"]["sourceChanges"][::-1]:
                del test_method[tc["lineNo"] - start_line]
            test_method.insert(target_line, patch)
            contents = contents.replace(test["aSource"]["code"], "\n".join(test_method))

    with open(test_file, "w") as orig_file:
        orig_file.write(contents)

    return original_contents


def apply_and_run_preds(preds, test, args):
    repo_name = test["ID"].split(":")[0]
    a_commit = test["aCommit"]

    worktree_path = gapi.copy_commit_code(repo_name, a_commit, test["ID"].split(":")[-1])

    verdicts = []
    for i, pred in tqdm(
        preds.iterrows(),
        total=len(preds),
        ascii=True,
        desc="Executing tests",
    ):
        pred_code = pred["pred"]
        target_code = pred["target"]
        if pred_code == target_code:
            verdict = mvnp.TestVerdict(mvnp.TestVerdict.SUCCESS, None).to_dict()
        else:
            test_rel_path = Path(test["aPath"])
            test_file = worktree_path / test_rel_path
            original_contents = apply_patch(pred_code, test, test_file, args.edit_sequence)
            if original_contents is None and args.edit_sequence:
                verdict = mvnp.TestVerdict(mvnp.TestVerdict.INVALID_EDIT_SEQUENCE, None).to_dict()
            else:
                _, class_name, test_short_name = decompose_full_method_name(test["name"])
                log_path = (
                    args.output_path
                    / "testLogs"
                    / test["aCommit"]
                    / class_name
                    / test_short_name
                    / test_rel_path.parent
                    / str(pred["rank"])
                )
                timeout = 15 * 60 if i > 2 else 240 * 60
                verdict = mvnp.compile_and_run_test(
                    worktree_path, test_rel_path, test_short_name, log_path, not args.discard_logs, timeout=timeout
                )
                verdict = verdict.to_dict()
                with open(test_file, "w") as orig_file:
                    orig_file.write(original_contents)

        verdicts.append((verdict, pred["id"], pred["rank"]))

    gapi.remove_commit_code(repo_name, worktree_path)

    return verdicts


if __name__ == "__main__":
    main()
