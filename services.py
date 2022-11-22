from pathlib import Path
import pandas as pd
import github_api as ghapi
from tqdm import tqdm
import json
from config import Config
from tag_analysis import TagPair
from code_analysis import (
    create_repaired_tc_call_graphs,
    create_repaired_tc_change_coverage,
    get_test_method_coverage,
    mine_method_refactorings,
)
import copy


class Service:
    @staticmethod
    def analyze_tag_and_repairs():
        tags, tag_parents = ghapi.get_tags_and_ancestors(Config.get("repo"))

        class_info_l = []
        method_info_l = []
        for tag, parent in tqdm(tag_parents.items()):
            head = tags[tag]
            base = tags[parent] if parent else None

            if not base:
                continue  # Occurs when there is no ancestor to the head tag

            print()
            print(f"Analyzing tag pair {base.name}...{head.name}")
            tag_pair = TagPair(base, head)
            class_info, method_info = tag_pair.extract_tag_repairs()
            if class_info.empty or method_info.empty:
                continue
            class_info_l.append(class_info)
            method_info_l.append(method_info)

        pd.concat(class_info_l).to_csv(
            Path(Config.get("output_path")) / "tags" / "changed_test_classes.csv",
            index=False,
        )
        pd.concat(method_info_l).to_csv(
            Path(Config.get("output_path")) / "repairs" / "repaired_test_methods.csv",
            index=False,
        )

    @staticmethod
    def get_test_code(tag, _class, method):
        base_path = Path(Config.get("output_path")) / "tags" / tag / "changed_tests" / _class
        code = (base_path / "methods" / method).read_text()
        body_code = (base_path / "methodBodies" / method).read_text()
        return code, body_code

    @staticmethod
    def create_dataset():
        create_repaired_tc_call_graphs()
        create_repaired_tc_change_coverage()
        refactorings = mine_method_refactorings()
        refactorings = {tag_pair: set([r["method"] for r in mrefs]) for tag_pair, mrefs in refactorings.items()}

        repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "repaired_test_methods.csv")
        full_changed_methods = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_coverage_changed_methods.json").read_text()
        )
        changed_methods = {r["baseTag"]: r["methodChanges"] for r in full_changed_methods}

        test_repair_changes = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_repair_changes.json").read_text()
        )
        repair_changes_map = {f"{ch['baseTag']}-{ch['headTag']}-{ch['name']}": ch["hunks"] for ch in test_repair_changes}

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
                tests = pd.read_csv(Path(Config.get("output_path")) / "tags" / base_tag / "tests.csv")
                test_paths[base_tag] = dict(zip(tests["NAME"].values.tolist(), tests["PATH"].values.tolist()))
            path = test_paths[base_tag][_class]
            before_repair, before_repair_body = Service.get_test_code(base_tag, _class, method)
            after_repair, after_repair_body = Service.get_test_code(head_tag, _class, method)
            method_coverage = get_test_method_coverage(_class, method, base_tag)
            if method_coverage is None:
                print(f"No call graph found for {name} ! Skipping ...")
                continue

            refactored_methods = refactorings[(base_tag, head_tag)]
            covered_changes = []
            for change in changed_methods.get(base_tag, []):
                found_coverage_i = [i for i, mc in enumerate(method_coverage) if mc["name"] == change["name"]]
                if len(found_coverage_i) > 0 and len(change["hunks"]) > 0:
                    _change = copy.deepcopy(change)
                    _change["depth"] = method_coverage[found_coverage_i[0]]["depth"]
                    _change["refactor"] = _change["name"] in refactored_methods
                    covered_changes.append(_change)
            repair_changes = repair_changes_map[f"{base_tag}-{head_tag}-{name}"]

            dataset.append(
                {
                    "name": name,
                    "path": path,
                    "base_tag": base_tag,
                    "head_tag": head_tag,
                    "before_repair": before_repair,
                    "before_repair_body": before_repair_body,
                    "after_repair": after_repair,
                    "after_repair_body": after_repair_body,
                    "covered_changes": covered_changes,
                    "repair_changes": repair_changes,
                    "refactor": name in refactored_methods,
                }
            )

        (Path(Config.get("output_path")) / "dataset.json").write_text(
            json.dumps(dataset, indent=2, sort_keys=False), encoding="utf-8"
        )
