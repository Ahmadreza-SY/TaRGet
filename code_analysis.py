import pickle
from pathlib import Path
import pandas as pd
import jparser
from tqdm import tqdm
import json
from config import Config


def create_repaired_tc_call_graphs():
    repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv")
    base_tags = repair_info["base_tag"].unique()
    for base_tag in tqdm(base_tags, ncols=100, position=0, leave=True, desc="Creating call graphs"):
        jparser.create_call_graphs(Path(Config.get("output_path")), base_tag)


def get_call_graph(_class, method, tag):
    call_graph_path = Path(Config.get("output_path")) / "releases" / tag / "call_graphs" / _class / f"{method}.json"
    call_graph = {}
    with open(call_graph_path) as f:
        call_graph = json.loads(f.read())

    return call_graph


def get_test_file_coverage(_class, method, tag):
    all_tests = pd.read_csv(Path(Config.get("output_path")) / "releases" / tag / "tests.csv")
    all_test_files = all_tests["PATH"].values.tolist()

    call_graph = get_call_graph(_class, method, tag)

    return set([n["path"] for n in call_graph["nodes"] if n["path"] not in all_test_files])


def get_release_changed_files(base_tag, head_tag):
    release_patches_path = Path(Config.get("output_path")) / "repairs" / f"{base_tag}...{head_tag}" / "patches.pickle"
    patches = pickle.load(open(str(release_patches_path), "rb"))
    return set([patch.path for patch in patches["patches"].modified_files])


def create_repaired_tc_change_coverage():
    repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv")

    change_coverage = []
    for _, r in tqdm(
        repair_info.iterrows(),
        total=len(repair_info),
        ncols=100,
        position=0,
        leave=True,
        desc="Creating test change coverage",
    ):
        _class, method, base_tag, head_tag = (
            r["class"],
            r["method"],
            r["base_tag"],
            r["head_tag"],
        )
        tc_coverage = get_test_file_coverage(_class, method, base_tag)
        changed_files = get_release_changed_files(base_tag, head_tag)
        tc_change_coverage = list(tc_coverage.intersection(changed_files))
        if len(tc_coverage) == 0:
            cov_per = 0.0
        else:
            cov_per = len(tc_change_coverage) / len(tc_coverage)
        chn_per = len(tc_change_coverage) / len(changed_files)
        change_coverage.append(
            {
                "test": f"{_class}.{method}",
                "baseTag": base_tag,
                "headTag": head_tag,
                "covered_changed_files": tc_change_coverage,
                "coverage_percentage": f"{cov_per:.2f}",
                "change_percentage": f"{chn_per:.3f}",
            }
        )

    cov_output_file = Path(Config.get("output_path")) / "repairs" / "test_change_coverage.json"
    with open(cov_output_file, "w") as f:
        f.write(json.dumps(change_coverage))

    jparser.detect_changed_methods(Config.get("output_path"))


def get_test_method_coverage(_class, method, tag):
    call_graph = get_call_graph(_class, method, tag)
    return set([n["name"] for n in call_graph["nodes"]])