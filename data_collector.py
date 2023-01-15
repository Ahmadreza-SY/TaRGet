from pathlib import Path
import pandas as pd
import git_api as ghapi
from tqdm import tqdm
import json
import copy
import re
from tqdm import tqdm
from utils import save_file, is_test_class
import jparser
import shutil
import maven_parser as mvnp
from coverage_repository import ClassChangesRepository, MethodChangesRepository
import multiprocessing as mp


def pool_init(_lock):
    global lock
    lock = _lock


class DataCollector:
    def __init__(self, repo_name, output_path):
        self.repo_name = repo_name
        self.output_path = Path(output_path)

    def collect_test_repairs(self):
        print("Phase #1: Identifying changed tests and extracting their changes")
        self.identify_changed_test_classes()
        jparser.compare_test_classes(self.output_path)
        print()

        print("Phase #2: Detecting broken tests by executing them")
        repaired_tests = self.detect_repaired_tests()
        print()

        print("Phase #3: Identifying and extracting covered changes")
        repair_commits = set([(r["bCommit"], r["aCommit"]) for r in repaired_tests])
        self.find_changed_sut_classes(repair_commits)
        jparser.extract_covered_changes_info(self.output_path)
        print()

        self.make_dataset(repaired_tests)

    def get_java_diffs(self, commit):
        diffs = commit.diff(commit.parents[0].hexsha)
        # Interested in renamed and modified paths
        diffs = [d for d in diffs if d.change_type in ["R", "M"]]
        java_regex = r"^.*\.java$"
        diffs = [d for d in diffs if bool(re.search(java_regex, d.b_path)) and bool(re.search(java_regex, d.a_path))]
        return diffs

    def identify_changed_test_classes(self):
        changed_test_classes_path = self.output_path / "changed_test_classes.csv"
        if changed_test_classes_path.exists():
            print("Changed tests classes already exists, skipping ...")
            return
        commits = ghapi.get_all_commits(self.repo_name)

        changed_test_classes = {"b_path": [], "a_path": [], "b_commit": [], "a_commit": []}
        for commit in tqdm(commits, ascii=True, desc="Identifying changed test classes"):
            if len(commit.parents) == 0:
                continue
            diffs = self.get_java_diffs(commit)
            for diff in diffs:
                before, after = ghapi.get_file_versions(diff, commit, self.repo_name)
                if is_test_class(before) and before != after:
                    b_commit = ghapi.get_short_commit(commit.parents[0], self.repo_name)
                    a_commit = ghapi.get_short_commit(commit, self.repo_name)
                    changed_test_classes["b_path"].append(diff.b_path)
                    changed_test_classes["a_path"].append(diff.a_path)
                    changed_test_classes["b_commit"].append(b_commit)
                    changed_test_classes["a_commit"].append(a_commit)
                    b_copy_path = self.output_path / "testClasses" / b_commit / diff.b_path
                    a_copy_path = self.output_path / "testClasses" / a_commit / diff.a_path
                    save_file(before, b_copy_path)
                    save_file(after, a_copy_path)

        changed_test_classes = pd.DataFrame(changed_test_classes)
        changed_test_classes.to_csv(changed_test_classes_path, index=False)

    def run_changed_tests(self, change_group):
        changed_tests_verdicts = []
        repaired_tests = []
        (a_commit, changes) = change_group
        a_commit_path = self.output_path / "commits" / a_commit

        lock.acquire()
        ghapi.copy_commit_code(self.repo_name, a_commit)
        lock.release()

        for _, change in changes.iterrows():
            test_simple_name = change["name"].split(".")[-1].replace("()", "")
            test_a_path = Path(change["aPath"])
            original_file = self.output_path / "testClasses" / a_commit / test_a_path
            broken_file = self.output_path / "brokenPatches" / a_commit / original_file.stem / test_simple_name / test_a_path
            log_path = (
                self.output_path / "brokenExeLogs" / a_commit / original_file.stem / test_simple_name / test_a_path.parent
            )
            executable_file = a_commit_path / test_a_path
            shutil.copyfile(str(broken_file), str(executable_file))
            verdict = mvnp.compile_and_run_test(a_commit_path, test_a_path, test_simple_name, log_path)
            verdict_obj = {
                "status": verdict.status,
                "error_lines": None if not verdict.error_lines else sorted(list(verdict.error_lines)),
            }
            changed_tests_verdicts.append(
                {
                    "name": change["name"],
                    "aCommit": change["aCommit"],
                    "verdict": verdict_obj,
                }
            )
            if verdict.is_valid() and verdict.status != mvnp.TestVerdict.SUCCESS:
                change_obj = change.to_dict()
                change_obj["verdict"] = verdict_obj
                repaired_tests.append(change_obj)
            shutil.copyfile(str(original_file), str(executable_file))

        lock.acquire()
        ghapi.remove_commit_code(self.repo_name, a_commit)
        lock.release()

        return changed_tests_verdicts, repaired_tests

    def detect_repaired_tests(self):
        changed_tests_verdicts_path = self.output_path / "changed_tests_verdicts.json"
        repaired_tests_path = self.output_path / "repaired_tests.json"
        if changed_tests_verdicts_path.exists() and repaired_tests_path.exists():
            print("Tests have been already executed, skipping ...")
            return json.loads(repaired_tests_path.read_text())

        changed_tests = pd.read_json(self.output_path / "changed_tests.json")
        change_groups = list(changed_tests.groupby("aCommit"))
        changed_tests_cnt = sum([len(g[1]) for g in change_groups])

        ghapi.cleanup_worktrees(self.repo_name)

        changed_tests_verdicts = []
        repaired_tests = []

        proc_cnt = (1 + mp.cpu_count() // 2) if mp.cpu_count() > 2 else mp.cpu_count()
        with mp.Pool(proc_cnt, initializer=pool_init, initargs=(mp.Lock(),)) as pool:
            for verdicts, repaired in tqdm(
                pool.imap_unordered(self.run_changed_tests, change_groups),
                total=len(change_groups),
                ascii=True,
                desc="Executing tests",
            ):
                changed_tests_verdicts.extend(verdicts)
                repaired_tests.extend(repaired)

        changed_tests_verdicts_path.write_text(json.dumps(changed_tests_verdicts, indent=2, sort_keys=False))
        print(f"Executed {changed_tests_cnt} test cases! Verdict stats:")
        verdict_df = pd.DataFrame({"verdict": [v["verdict"]["status"] for v in changed_tests_verdicts]})
        for v, cnt in verdict_df["verdict"].value_counts().items():
            print(f"  {v} -> {round(100*cnt/len(verdict_df), 1)}% ({cnt})")

        non_broken_cnt = changed_tests_cnt - len(repaired_tests)
        print(
            f"{round(100*non_broken_cnt/changed_tests_cnt, 1)}% ({non_broken_cnt}/{changed_tests_cnt}) of changed tests were not broken!"
        )
        print(f"Found {len(repaired_tests)} repaired tests")
        repaired_tests_path.write_text(json.dumps(repaired_tests, indent=2, sort_keys=False))

        return repaired_tests

    def find_changed_sut_classes(self, commits):
        changed_sut_classes_path = self.output_path / "changed_sut_classes.json"
        if changed_sut_classes_path.exists():
            print("Changed SUT classes already exists, skipping ...")
            return

        repo = ghapi.get_repo(self.repo_name)
        changed_test_classes = pd.read_csv(self.output_path / "changed_test_classes.csv")
        changed_test_class_paths = set(
            changed_test_classes["b_path"].values.tolist() + changed_test_classes["a_path"].values.tolist()
        )
        changed_classes = []
        for b_commit, a_commit in tqdm(commits, ascii=True, desc="Finding changed classes in the SUT"):
            diffs = self.get_java_diffs(repo.commit(a_commit))
            commit_changed_classes = []
            for diff in diffs:
                if diff.a_path in changed_test_class_paths or diff.b_path in changed_test_class_paths:
                    continue
                commit_changed_classes.append((diff.b_path, diff.a_path))
            changed_classes.append({"bCommit": b_commit, "aCommit": a_commit, "changedClasses": commit_changed_classes})

        changed_sut_classes_path.write_text(json.dumps(changed_classes, indent=2, sort_keys=False))

    def make_dataset(self, repaired_tests):
        class_change_repo = ClassChangesRepository(self.output_path)
        method_change_repo = MethodChangesRepository(self.output_path)
        zero_cov_cnt = 0
        dataset = []
        for repair in repaired_tests:
            _repair = copy.deepcopy(repair)
            covered_class_changes = class_change_repo.get_covered_changes(_repair)
            covered_method_changes = method_change_repo.get_covered_changes(_repair)
            if len(covered_class_changes) == 0 and len(covered_method_changes) == 0:
                zero_cov_cnt += 1
                continue

            _repair["covered_class_changes"] = covered_class_changes
            _repair["covered_method_changes"] = covered_method_changes
            dataset.append(_repair)

        zero_cov_per = round(100 * zero_cov_cnt / len(repaired_tests), 1)
        print(f"Removed {zero_cov_per}% ({zero_cov_cnt} / {len(repaired_tests)}) repairs due to zero coverage.")
        (self.output_path / "dataset.json").write_text(json.dumps(dataset, indent=2, sort_keys=False))
        print(f"Done! Saved {len(dataset)} test repairs.")
