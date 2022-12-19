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
    is_test_class,
)
import copy
import re
from tqdm import tqdm
from utils import save_file
import jparser
import shutil
import maven_parser as mvnp


class Service:
    @staticmethod
    def analyze_repair_commits():
        repo_name = Config.get("repo")
        commits = ghapi.get_all_commits(repo_name)
        output_path = Path(Config.get("output_path"))
        changed_test_classes = {"b_path": [], "a_path": [], "b_commit": [], "a_commit": []}
        for commit in tqdm(commits[:100]):
            if len(commit.parents) == 0:
                continue
            diffs = commit.diff(commit.parents[0].hexsha)
            # Interested in renamed and modified paths
            diffs = [d for d in diffs if d.change_type in ["R", "M"]]
            java_regex = r"^.*\.java$"
            diffs = [d for d in diffs if bool(re.search(java_regex, d.b_path)) and bool(re.search(java_regex, d.a_path))]
            for diff in diffs:
                before, after = ghapi.get_file_versions(diff, commit, repo_name)
                if is_test_class(before) and before != after:
                    b_commit = ghapi.get_short_commit(commit.parents[0], repo_name)
                    a_commit = ghapi.get_short_commit(commit, repo_name)
                    changed_test_classes["b_path"].append(diff.b_path)
                    changed_test_classes["a_path"].append(diff.a_path)
                    changed_test_classes["b_commit"].append(b_commit)
                    changed_test_classes["a_commit"].append(a_commit)
                    b_copy_path = output_path / "commits" / b_commit / diff.b_path
                    a_copy_path = output_path / "commits" / a_commit / diff.a_path
                    save_file(before, b_copy_path)
                    save_file(after, a_copy_path)

        changed_test_classes = pd.DataFrame(changed_test_classes)
        changed_test_classes.to_csv(output_path / "changed_test_classes.csv", index=False)

        jparser.compare_test_classes(output_path)

        changed_tests = pd.read_json(output_path / "changed_tests.json")
        pbar = tqdm(total=len(changed_tests), ascii=True)
        changed_tests_verdicts = []
        for commit, repairs in changed_tests.groupby("aCommit"):
            repo = ghapi.get_repo(repo_name)
            repo.git.checkout(commit, force=True)
            for _, repair in repairs.iterrows():
                test_simple_name = repair["name"].split(".")[-1].replace("()", "")
                original_file = output_path / "commits" / commit / repair["aPath"]
                broken_file = (
                    output_path / "brokenPatches" / commit / original_file.stem / test_simple_name / repair["aPath"]
                )
                log_path = (
                    output_path
                    / "brokenExeLogs"
                    / commit
                    / original_file.stem
                    / test_simple_name
                    / Path(repair["aPath"]).parent
                )
                repo_path = Path(repo.working_tree_dir)
                executable_file = repo_path / repair["aPath"]
                shutil.copyfile(str(broken_file), str(executable_file))
                pbar.set_description(f"Executing {original_file.stem}#{test_simple_name} at {commit}")
                verdict = mvnp.compile_and_run_test(repo_path, repair["aPath"], test_simple_name, log_path)
                changed_tests_verdicts.append(
                    {
                        "name": repair["name"],
                        "aCommit": repair["aCommit"],
                        "verdict": {
                            "status": verdict.status,
                            "error_lines": None if not verdict.error_lines else sorted(list(verdict.error_lines)),
                        },
                    }
                )
                shutil.copyfile(str(original_file), str(executable_file))
                pbar.update(1)

        (output_path / "changed_tests_verdicts.json").write_text(
            json.dumps(changed_tests_verdicts, indent=2, sort_keys=False)
        )
        # extract call graphs of changed test methods
        # create test covered diff
        # save results

    @staticmethod
    def analyze_tag_and_repairs():
        tags, tag_ancestors = ghapi.get_tags_and_ancestors(Config.get("repo"))

        class_info_l = []
        method_info_l = []
        for tag, ancestor in tqdm(tag_ancestors):
            head = tags[tag]
            base = tags[ancestor]
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
    def create_test_repair(repair_info, features):
        _class, method, base_tag, head_tag = (
            repair_info["class"],
            repair_info["method"],
            repair_info["base_tag"],
            repair_info["head_tag"],
        )
        test_paths, changed_methods, refactored_methods, refactor_types, repair_changes = (
            features["test_paths"],
            features["changed_methods"],
            features["refactored_methods"],
            features["refactor_types"],
            features["repair_changes"],
        )
        name = f"{_class}.{method}"
        path = test_paths[base_tag][_class]
        before_repair, before_repair_body = Service.get_test_code(base_tag, _class, method)
        after_repair, after_repair_body = Service.get_test_code(head_tag, _class, method)
        method_coverage = get_test_method_coverage(_class, method, base_tag)
        if method_coverage is None:
            # print(f"No call graph found for {name} ! Skipping ...")
            return None

        tag_pair = (base_tag, head_tag)
        covered_changes = []
        for change in changed_methods.get(base_tag, []):
            found_coverage_i = [i for i, mc in enumerate(method_coverage) if mc["name"] == change["name"]]
            if len(found_coverage_i) > 0 and len(change["hunks"]) > 0:
                _change = copy.deepcopy(change)
                _change["depth"] = method_coverage[found_coverage_i[0]]["depth"]
                _change["refactor"] = _change["name"] in refactored_methods[tag_pair]
                _change["refactor_types"] = None if not _change["refactor"] else refactor_types[tag_pair][_change["name"]]
                covered_changes.append(_change)
        repair_changes = repair_changes[f"{base_tag}-{head_tag}-{name}"]

        test_refactored = name in refactored_methods[tag_pair]
        return {
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
            "refactor": test_refactored,
            "refactor_types": None if not test_refactored else refactor_types[tag_pair][name],
        }

    @staticmethod
    def compute_features():
        create_repaired_tc_call_graphs()
        create_repaired_tc_change_coverage()
        refactorings = mine_method_refactorings()

        refactored_methods = {tag_pair: set([r["method"] for r in mrefs]) for tag_pair, mrefs in refactorings.items()}
        refactor_types = {}
        for tag_pair, mrefs in refactorings.items():
            tag_refactor_types = {}
            for mref in mrefs:
                method_refactor_types = []
                for c in mref["refactoringCommits"]:
                    method_refactor_types.extend(c["refactorings"])
                tag_refactor_types[mref["method"]] = method_refactor_types
            refactor_types[tag_pair] = tag_refactor_types

        repair_info = pd.read_csv(Path(Config.get("output_path")) / "repairs" / "repaired_test_methods.csv")
        test_paths = {}
        for _, r in repair_info.iterrows():
            base_tag = r["base_tag"]
            if base_tag not in test_paths:
                tests = pd.read_csv(Path(Config.get("output_path")) / "tags" / base_tag / "tests.csv")
                test_paths[base_tag] = dict(zip(tests["NAME"].values.tolist(), tests["PATH"].values.tolist()))

        full_changed_methods = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_coverage_changed_methods.json").read_text()
        )
        changed_methods = {r["baseTag"]: r["methodChanges"] for r in full_changed_methods}

        test_repair_changes = json.loads(
            (Path(Config.get("output_path")) / "repairs" / "test_repair_changes.json").read_text()
        )
        repair_changes = {f"{ch['baseTag']}-{ch['headTag']}-{ch['name']}": ch["hunks"] for ch in test_repair_changes}

        return {
            "repair_info": repair_info,
            "refactored_methods": refactored_methods,
            "refactor_types": refactor_types,
            "test_paths": test_paths,
            "changed_methods": changed_methods,
            "repair_changes": repair_changes,
        }

    @staticmethod
    def create_dataset():
        features = Service.compute_features()

        dataset = []
        repair_info = features["repair_info"]
        for _, r in tqdm(
            repair_info.iterrows(),
            total=len(repair_info),
            ascii=True,
            desc="Creating dataset",
        ):
            repair = Service.create_test_repair(r, features)
            if repair is not None:
                dataset.append(repair)

        (Path(Config.get("output_path")) / "dataset.json").write_text(
            json.dumps(dataset, indent=2, sort_keys=False), encoding="utf-8"
        )
