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
import time

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
    args = parser.parse_args()
    args.output_path = Path(args.output_path)
    Config.set("output_path", args.output_path)
    Config.set("repo_path", args.repo_path)
    Config.set("java_homes_path", args.java_homes)
    Config.set("m2_path", args.m2_path)

    test_ds = json.loads((args.output_path / "splits" / "test.json").read_text())
    test_preds = json.loads((args.output_path / "test_predictions.json").read_text())
    selected_test = test_ds[args.test_index]
    selected_pred = next((pred for pred in test_preds if pred["ID"] == selected_test["ID"]), None)

    logger.info(
        f"Starting to execute {len(selected_pred['preds'])} candidate repair patches for test ID {selected_test['ID']}"
    )
    verdicts = apply_and_run_preds(selected_pred, selected_test, args)

    verdict_df, _ = analyze_verdicts(verdicts)
    if len(verdict_df) > 0:
        verdicts_file = args.output_path / "test_verdicts" / f"{args.test_index}.json"
        verdicts_file.parent.mkdir(exist_ok=True, parents=True)
        verdict_df.to_json(verdicts_file, orient="records", indent=2)
        logger.info(f"Execution finished!")


def analyze_verdicts(verdicts):
    if len(verdicts) == 0:
        return pd.DataFrame({}), -1
    vs_df = pd.DataFrame({"verdict": [r["verdict"]["status"] for r in verdicts]})
    logger.info("Verdict stats:")
    for v, cnt in vs_df["verdict"].value_counts().items():
        print(f"    {v} -> {round(100*cnt/len(vs_df), 1)}% ({cnt})")

    verdict_df = pd.DataFrame(verdicts)
    verdict_df["success"] = verdict_df["verdict"].apply(lambda v: 1 if v["status"] == mvnp.TestVerdict.SUCCESS else 0)
    success_cnt = verdict_df.groupby("id").filter(lambda g: g["success"].sum() >= 1)["id"].nunique()
    plausible_rate = round(100 * success_cnt / verdict_df["id"].nunique(), 1)
    logger.info(f"Plausible Rate: {plausible_rate} %")

    return verdict_df, plausible_rate


def apply_patch(patch, test, test_file):
    with open(test_file, "r") as orig_file:
        original_contents = orig_file.read()
    with open(test_file, "r") as orig_file:
        contents = orig_file.read()

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


def apply_and_run_preds(prediction, test, args):
    repo_name = test["ID"].split(":")[0]
    a_commit = test["aCommit"]

    worktree_path = gapi.copy_commit_code(repo_name, a_commit, test["ID"].split(":")[-1])

    verdicts = []
    verdict_cache = {}
    preds = prediction["preds"]
    target = prediction["target"]
    invalid_verdict_cnt = 0
    for i, candidate in tqdm(enumerate(preds), ascii=True, total=len(preds), desc="Executing tests"):
        rank = i
        candidate = candidate.strip()
        exec_time = 0.0
        start_time = time.time()
        if candidate == target:
            verdict = mvnp.TestVerdict(mvnp.TestVerdict.SUCCESS, None)
        elif candidate in verdict_cache:
            verdict = verdict_cache[candidate]
        else:
            test_rel_path = Path(test["aPath"])
            test_file = worktree_path / test_rel_path
            original_contents = apply_patch(candidate, test, test_file)
            _, class_name, test_short_name = decompose_full_method_name(test["name"])
            log_path = (
                args.output_path
                / "testLogs"
                / test["aCommit"]
                / class_name
                / test_short_name
                / test_rel_path.parent
                / str(rank)
            )
            timeout = 30 * 60
            verdict = mvnp.compile_and_run_test(
                worktree_path, test_rel_path, test_short_name, log_path, not args.discard_logs, timeout=timeout
            )
            if not verdict.is_valid() and verdict.log is not None:
                java_version = verdict.log.splitlines()[2].split("=")[1].split("/")[-1].split(".")[0]
                if java_version != "11":
                    print(f"Got {verdict} with Java {java_version}, re-executing with Java 11")
                    log_file = log_path / "test.log"
                    if log_file.exists():
                        log_file.unlink()
                    verdict = mvnp.compile_and_run_test(
                        worktree_path,
                        test_rel_path,
                        test_short_name,
                        log_path,
                        not args.discard_logs,
                        timeout=timeout,
                        java_version="11",
                    )
            verdict_cache[candidate] = verdict
            with open(test_file, "w") as orig_file:
                orig_file.write(original_contents)
            exec_time = time.time() - start_time

        if verdict.status in [mvnp.TestVerdict.TIMEOUT, mvnp.TestVerdict.DEPENDENCY_ERROR]:
            invalid_verdict_cnt += 1
        verdicts.append({"verdict": verdict.to_dict(), "id": prediction["ID"], "rank": rank, "exec_time": exec_time})

    gapi.remove_commit_code(repo_name, worktree_path)

    if len(verdicts) > 1 and invalid_verdict_cnt / len(verdicts) >= 0.75:
        analyze_verdicts(verdicts)
        print(f"Not saving test verdicts due to {invalid_verdict_cnt} invalid verdicts.")
        return []

    return verdicts


if __name__ == "__main__":
    main()
