import sys

sys.path.append("../common")
import argparse
import logging
import json
import git
import re
from tqdm import tqdm
from pathlib import Path
import pandas as pd
import multiprocessing as mp
from encoders.testRepair.testRepair import Tokens
from common_utils import decompose_full_method_name
from config import Config
import maven_parser as mvnp
import git_api as gapi

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%m-%d-%Y %H:%M:%S",
    level=logging.INFO,
)


def pool_init(_lock, _test_ds, _args):
    global lock, test_ds, args
    lock = _lock
    test_ds = _test_ds
    args = _args


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
        "--java-home",
        help="The home of Java for executing test cases of the repository. If not passed, Maven's default java home will be used.",
        type=str,
        required=False,
        default=None,
    )
    logger = logging.getLogger("MAIN")
    args = parser.parse_args()
    args.output_path = Path(args.output_path)
    Config.set("output_path", args.output_path)
    Config.set("repo_path", args.repo_path)
    Config.set("java_home", args.java_home)

    pred_file = args.output_path / "test_predictions.json"
    pred_df = pd.read_json(pred_file)
    test_ds = {row["ID"]: row for row in json.loads((args.output_path / "splits" / f"test.json").read_text())}
    pred_groups = list(pred_df.groupby("id"))
    args.repo_name = next(iter(test_ds)).split(":")[0]
    gapi.cleanup_worktrees(args.repo_name)
    logger.info(f"Starting to execute {len(pred_df)} candidate repair patches")
    results = []
    proc_cnt = round(mp.cpu_count() / 4) if mp.cpu_count() > 2 else 1
    with mp.Pool(proc_cnt, initializer=pool_init, initargs=(mp.Lock(), test_ds, args)) as pool:
        for res in tqdm(
            pool.imap_unordered(apply_and_run_preds, pred_groups),
            total=len(pred_groups),
            ascii=True,
            desc="Executing tests",
        ):
            results.extend(res)

    logger.info(f"Execution finished!")
    vs_df = pd.DataFrame({"verdict": [r[0]["status"] for r in results]})
    logger.info("Verdict stats:")
    for v, cnt in vs_df["verdict"].value_counts().items():
        print(f"    {v} -> {round(100*cnt/len(vs_df), 1)}% ({cnt})")
    
    verdict_df = pd.DataFrame(
        {"verdict": [r[0] for r in results], "id": [r[1] for r in results], "rank": [r[2] for r in results]}
    )
    verdict_df["success"] = verdict_df["verdict"].apply(lambda v: 1 if v["status"] == mvnp.TestVerdict.SUCCESS else 0)
    success_cnt = verdict_df.groupby("id").filter(lambda g: g["success"].sum() >= 1)["id"].nunique()
    success_rate = round(100 * success_cnt / verdict_df["id"].nunique(), 1)
    logger.info(f"Success Rate: {success_rate} %")
    verdict_df.to_json(args.output_path / "test_verdicts.json", orient="records", indent=2)


def get_breakage_from_input(input):
    matches = re.compile(f"^{Tokens.BREAKAGE} (.*) {Tokens.TEST_CONTEXT}.+$", re.MULTILINE).findall(input)
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly 1 match for breakage, found {len(matches)}! Input: {input}")
    return matches[0]


def apply_patch(patch, test, test_file):
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


def apply_and_run_preds(pred_group):
    (pred_id, preds) = pred_group
    test = test_ds[pred_id]
    a_commit = test['aCommit']

    lock.acquire()
    worktree_path = gapi.copy_commit_code(args.repo_name, a_commit)
    lock.release()
    worktree = git.Repo(worktree_path)

    verdicts = []
    for _, pred in preds.iterrows():
        test = test_ds[pred["id"]]
        breakage_code = get_breakage_from_input(test["input"])
        pred_code = pred["pred"]
        target_code = pred["target"]
        if pred_code == breakage_code:
            verdict = test["verdict"]
        elif pred_code == target_code:
            verdict = mvnp.TestVerdict(mvnp.TestVerdict.SUCCESS, None).to_dict()
        else:
            test_rel_path = Path(test["aPath"])
            test_file = worktree_path / test_rel_path
            apply_patch(pred_code, test, test_file)
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
            verdict = mvnp.compile_and_run_test(worktree_path, test_rel_path, test_short_name, log_path).to_dict()
            worktree.git.reset("--hard")

        verdicts.append((verdict, pred["id"], pred["rank"]))

    lock.acquire()
    gapi.remove_commit_code(args.repo_name, worktree_path)
    lock.release()

    return verdicts


if __name__ == "__main__":
    main()
