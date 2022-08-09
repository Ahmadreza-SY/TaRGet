from pathlib import Path
import pandas as pd
import github_api as ghapi
from tqdm import trange, tqdm
import json
from config import Config
from release_analysis import Release, ReleasePair
from code_analysis import create_repaired_tc_call_graphs, create_repaired_tc_change_coverage, get_test_method_coverage


class Service:
    @staticmethod
    def analyze_release_and_repairs():
        releases = [
            Release(r["name"], r["tag_name"], pd.to_datetime(r["created_at"]), r["tarball_url"])
            for r in ghapi.get_all_releases(Config.get("repo"))
        ]
        releases.sort(key=lambda r: r.date, reverse=True)
        rel_info_l = []
        rep_info_l = []
        for i in trange(len(releases) - 1, ncols=100, position=0, leave=True):
            head = releases[i]
            base = releases[i + 1]
            print()
            print(f"Analyzing release {base.tag}...{head.tag}")
            release_pair = ReleasePair(base, head)
            rel_info, rep_info = release_pair.extract_release_repairs()
            if rel_info.empty or rep_info.empty:
                continue
            rel_info_l.append(rel_info)
            rep_info_l.append(rep_info)

        pd.concat(rel_info_l).to_csv(
            Path(Config.get("output_path")) / "releases" / "test_release_info.csv",
            index=False,
        )
        pd.concat(rep_info_l).to_csv(
            Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv",
            index=False,
        )

    @staticmethod
    def create_dataset():
        create_repaired_tc_call_graphs()
        create_repaired_tc_change_coverage()

        repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv")
        full_changed_methods = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_coverage_changed_methods.json").read_text()
        )
        changed_methods = {r["baseTag"]: r["methodChanges"] for r in full_changed_methods}

        dataset = []
        test_paths = {}
        for _, r in tqdm(
            repair_info.iterrows(),
            total=len(repair_info),
            ncols=100,
            position=0,
            leave=True,
            desc="Creating dataset",
        ):
            _class, method, base_tag, head_tag = (
                r["class"],
                r["method"],
                r["base_tag"],
                r["head_tag"],
            )
            name = f"{_class}.{method}"
            if base_tag not in test_paths:
                tests = pd.read_csv(Path(Config.get("output_path")) / "releases" / base_tag / "tests.csv")
                test_paths[base_tag] = dict(zip(tests["NAME"].values.tolist(), tests["PATH"].values.tolist()))
            path = test_paths[base_tag][_class]
            before_repair = (
                Path(Config.get("output_path")) / "releases" / base_tag / "changed_tests" / _class / "methods" / method
            ).read_text()
            after_repair = (
                Path(Config.get("output_path")) / "releases" / head_tag / "changed_tests" / _class / "methods" / method
            ).read_text()
            method_coverage = get_test_method_coverage(_class, method, base_tag)
            covered_changes = [change for change in changed_methods.get(base_tag, []) if change["name"] in method_coverage]

            dataset.append(
                {
                    "name": name,
                    "path": path,
                    "base_release_tag": base_tag,
                    "head_release_tag": head_tag,
                    "before_repair": before_repair,
                    "after_repair": after_repair,
                    "covered_changes": covered_changes,
                }
            )

        (Path(Config.get("output_path")) / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")
