from pathlib import Path
import pandas as pd
import github_api as ghapi
from tqdm import trange, tqdm
import json
from config import Config
from release_analysis import Release, ReleasePair
from code_analysis import create_repaired_tc_call_graphs, create_repaired_tc_change_coverage, get_test_method_coverage
import copy


class Service:
    @staticmethod
    def analyze_release_and_repairs():
        releases = {r["tag_name"]: Release(r["name"], r["tag_name"], pd.to_datetime(r["created_at"]), r["tarball_url"])
                    for r in ghapi.get_all_releases(Config.get("repo"))
                    if not r["prerelease"]
                    }

        release_parents = ghapi.get_tag_tree(Config.get("repo"), releases.keys())

        rel_info_l = []
        rep_info_l = []
        for name, release in tqdm(releases.items()):
            head = release
            base = releases[release_parents[name]] if name in release_parents else None

            if not base:
                continue  # Occurs when there is no ancestor to the head tag

            print()
            print(f"Analyzing release {base.tag}...{head.tag}")
            release_pair = ReleasePair(base, head)
            rel_info, rep_info = release_pair.extract_release_repairs()
            if rel_info.empty or rep_info.empty:
                continue
            rel_info_l.append(rel_info)
            rep_info_l.append(rep_info)
            return

        pd.concat(rel_info_l).to_csv(
            Path(Config.get("output_path")) / "releases" / "test_release_info.csv",
            index=False,
        )
        pd.concat(rep_info_l).to_csv(
            Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv",
            index=False,
        )

    @staticmethod
    def get_test_code(tag, _class, method):
        base_path = Path(Config.get("output_path")) / "releases" / tag / "changed_tests" / _class
        code = (base_path / "methods" / method).read_text()
        body_code = (base_path / "methodBodies" / method).read_text()
        return code, body_code

    @staticmethod
    def create_dataset():
        create_repaired_tc_call_graphs()
        create_repaired_tc_change_coverage()

        repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv")
        full_changed_methods = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_coverage_changed_methods.json").read_text()
        )
        changed_methods = {r["baseTag"]: r["methodChanges"] for r in full_changed_methods}

        test_repair_changes = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_repair_changes.json").read_text()
        )
        repair_changes_map = {f"{ch['baseTag']}-{ch['headTag']}-{ch['name']}": ch["hunks"] for ch in
                              test_repair_changes}

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
            before_repair, before_repair_body = Service.get_test_code(base_tag, _class, method)
            after_repair, after_repair_body = Service.get_test_code(head_tag, _class, method)
            method_coverage = get_test_method_coverage(_class, method, base_tag)
            if method_coverage is None:
                print(f"No call graph found for {name} ! Skipping ...")
                continue

            covered_changes = []
            for change in changed_methods.get(base_tag, []):
                found_coverage_i = [i for i, mc in enumerate(method_coverage) if mc["name"] == change["name"]]
                if len(found_coverage_i) > 0 and len(change["hunks"]) > 0:
                    _change = copy.deepcopy(change)
                    _change["depth"] = method_coverage[found_coverage_i[0]]["depth"]
                    covered_changes.append(_change)
            repair_changes = repair_changes_map[f"{base_tag}-{head_tag}-{name}"]

            dataset.append(
                {
                    "name": name,
                    "path": path,
                    "base_release_tag": base_tag,
                    "head_release_tag": head_tag,
                    "before_repair": before_repair,
                    "before_repair_body": before_repair_body,
                    "after_repair": after_repair,
                    "after_repair_body": after_repair_body,
                    "covered_changes": covered_changes,
                    "repair_changes": repair_changes,
                }
            )

        (Path(Config.get("output_path")) / "dataset.json").write_text(json.dumps(dataset), encoding="utf-8")

