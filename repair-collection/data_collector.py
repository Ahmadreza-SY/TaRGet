from pathlib import Path
import pandas as pd
import git_api as ghapi
from tqdm import tqdm
import json
import copy
from utils import (
    save_file,
    is_test_class,
    get_java_diffs,
    hunk_to_string,
    get_short_hash,
)
import jparser
import shutil
import maven_parser as mvnp
from coverage_repository import MethodChangesRepository
import multiprocessing as mp
from trivial_detector import TrivialDetector
from error_stats import ErrorStats
import sys


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
        if len(repaired_tests) == 0:
            print("No repaired tests found")
            return
        print()

        print("Phase #3: Identifying and extracting covered changes")
        repair_commits = set([(r["bCommit"], r["aCommit"]) for r in repaired_tests])
        self.find_changed_sut_classes(repair_commits)
        jparser.extract_covered_changes_info(self.output_path)
        self.label_changed_test_sources()
        ghapi.cleanup_worktrees(self.repo_name)
        print()

        self.make_dataset(repaired_tests)

        ErrorStats.report()

    def get_commit_changed_test_classes(self, commit_sha):
        commit = ghapi.get_commit(commit_sha, self.repo_name)
        if commit is None:
            (self.output_path / "codeMining" / "missing_commits.csv").open("a").write(commit_sha + "\n")
            return []
        if len(commit.parents) == 0:
            return []

        commit_changed_test_classes = []
        diffs = get_java_diffs(commit, ["R", "M"])
        for diff in diffs:
            before, after = ghapi.get_file_versions(diff, commit, self.repo_name)
            if is_test_class(before) and before != after:
                b_commit = commit.parents[0].hexsha
                a_commit = commit.hexsha
                commit_changed_test_classes.append(
                    {"b_path": diff.b_path, "a_path": diff.a_path, "b_commit": b_commit, "a_commit": a_commit}
                )
                b_copy_path = self.output_path / "codeMining" / "testClasses" / b_commit / diff.b_path
                a_copy_path = self.output_path / "codeMining" / "testClasses" / a_commit / diff.a_path
                try:
                    save_file(before, b_copy_path)
                    save_file(after, a_copy_path)
                except UnicodeEncodeError:
                    lock.acquire()
                    b_commit_path = ghapi.copy_commit_code(self.repo_name, b_commit, "0")
                    b_copy_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(str(b_commit_path / diff.b_path), str(b_copy_path))
                    ghapi.remove_commit_code(self.repo_name, b_commit_path)

                    a_commit_path = ghapi.copy_commit_code(self.repo_name, a_commit, "0")
                    a_copy_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(str(a_commit_path / diff.a_path), str(a_copy_path))
                    ghapi.remove_commit_code(self.repo_name, a_commit_path)
                    lock.release()

        return commit_changed_test_classes

    def identify_changed_test_classes(self):
        changed_test_classes_path = self.output_path / "codeMining" / "changed_test_classes.csv"
        if changed_test_classes_path.exists():
            print("Changed tests classes already exists, skipping ...")
            return
        commits = ghapi.get_all_commits(self.repo_name)
        commits_sha = [c.hexsha for c in commits]

        changed_test_classes = []
        with mp.Pool(initializer=pool_init, initargs=(mp.Lock(),)) as pool:
            for commit_changed_test_classes in tqdm(
                pool.imap_unordered(self.get_commit_changed_test_classes, commits_sha),
                total=len(commits_sha),
                ascii=True,
                desc="Identifying changed test classes",
            ):
                changed_test_classes.extend(commit_changed_test_classes)

        changed_test_classes = pd.DataFrame(changed_test_classes)
        changed_test_classes.to_csv(changed_test_classes_path, index=False)

    def run_original_test(self, project_path, change):
        test_b_path = Path(change["bPath"])
        test_name = change["name"]
        b_commit = change["bCommit"]
        test_method_name = test_name.split(".")[-1].replace("()", "")
        log_path = Path(b_commit) / test_b_path.stem / test_method_name / get_short_hash(str(test_b_path.parent))
        original_log_path = self.output_path / "testExecution" / "originalExeLogs" / log_path

        verdict = mvnp.compile_and_run_test(project_path, test_b_path, test_method_name, original_log_path)
        return verdict, None

    def run_changed_tests(self, change_group):
        changed_tests_verdicts = []
        repaired_tests = []
        tests_coverage = []
        (a_commit, changes) = change_group
        changes = changes.reset_index(drop=True)
        b_commit = changes.iloc[0]["bCommit"]

        lock.acquire()
        a_commit_path = ghapi.copy_commit_code(self.repo_name, a_commit, "0")
        b_commit_path = ghapi.copy_commit_code(self.repo_name, b_commit, a_commit)
        lock.release()

        for _, change in changes.iterrows():
            test_name = change["name"]
            test_method_name = test_name.split(".")[-1].replace("()", "")
            test_a_path = Path(change["aPath"])
            original_file = self.output_path / "codeMining" / "testClasses" / a_commit / test_a_path
            if not original_file.exists():
                ErrorStats.update(ErrorStats.missing_tf, str(original_file))
                continue
            broken_file = (
                self.output_path
                / "codeMining"
                / "brokenPatches"
                / a_commit
                / original_file.stem
                / test_method_name
                / test_a_path
            )
            if not broken_file.exists():
                ErrorStats.update(ErrorStats.missing_tf, str(broken_file))
                continue
            log_path = Path(a_commit) / original_file.stem / test_method_name / get_short_hash(str(test_a_path.parent))

            # Running T on P to check original test success
            original_verdict, covered_lines = self.run_original_test(b_commit_path, change)
            if not original_verdict.succeeded():
                changed_tests_verdicts.append(
                    {
                        "name": test_name,
                        "aPath": change["aPath"],
                        "bPath": change["bPath"],
                        "aCommit": a_commit,
                        "bCommit": b_commit,
                        "original_verdict": original_verdict.to_dict(),
                    }
                )
                continue
            if covered_lines is not None:
                tests_coverage.append((b_commit, test_name, covered_lines))

            broken_log_path = self.output_path / "testExecution" / "brokenExeLogs" / log_path
            executable_file = a_commit_path / test_a_path
            shutil.copyfile(str(broken_file), str(executable_file))
            # Running T on P' to detect whether the test case is broken (needs repair)
            before_verdict = mvnp.compile_and_run_test(a_commit_path, test_a_path, test_method_name, broken_log_path)
            shutil.copyfile(str(original_file), str(executable_file))

            after_verdict = None
            repaired_log_path = self.output_path / "testExecution" / "repairedExeLogs" / log_path
            if before_verdict.is_broken():
                # Running T' on P' to detect whether test case is correctly repaired
                after_verdict = mvnp.compile_and_run_test(a_commit_path, test_a_path, test_method_name, repaired_log_path)
                if after_verdict.succeeded():
                    change_obj = change.to_dict()
                    change_obj["verdict"] = before_verdict.to_dict()
                    repaired_tests.append(change_obj)

            changed_tests_verdicts.append(
                {
                    "name": test_name,
                    "aPath": change["aPath"],
                    "bPath": change["bPath"],
                    "aCommit": a_commit,
                    "bCommit": b_commit,
                    "verdict": before_verdict.to_dict(),
                    "broken": before_verdict.is_broken(),
                    "correctly_repaired": after_verdict.succeeded() if after_verdict is not None else None,
                }
            )

        lock.acquire()
        ghapi.remove_commit_code(self.repo_name, a_commit_path)
        ghapi.remove_commit_code(self.repo_name, b_commit_path)
        lock.release()

        return changed_tests_verdicts, repaired_tests, tests_coverage

    def print_execution_stats(self, changed_tests_verdicts, repaired_tests, changed_tests_cnt):
        print(f"Executed {changed_tests_cnt} test cases!")
        print(f"Found {len(repaired_tests)} repaired tests")
        repair_per = round(100 * len(repaired_tests) / changed_tests_cnt, 1)
        print(
            f"{repair_per}% ({len(repaired_tests)}/{changed_tests_cnt}) of changed tests were broken and correctly repaired!"
        )
        verdict_df = pd.DataFrame(
            {
                "verdict": [v["verdict"]["status"] for v in changed_tests_verdicts if "verdict" in v],
                "correctly_repaired": [v["correctly_repaired"] for v in changed_tests_verdicts if "verdict" in v],
            }
        )
        print("Verdict stats:")
        for v, cnt in verdict_df["verdict"].value_counts().items():
            print(f"  {v} -> {round(100*cnt/len(verdict_df), 1)}% ({cnt})")

        print("Correctly repaired stats:")
        for v, cnt in verdict_df["correctly_repaired"].value_counts(dropna=False).items():
            print(f"  {v} -> {round(100*cnt/len(verdict_df), 1)}% ({cnt})")
        og_verdict_df = pd.DataFrame(
            {
                "verdict": [v["original_verdict"]["status"] for v in changed_tests_verdicts if "original_verdict" in v],
            }
        )
        print(f"{len(og_verdict_df)} test cases were originaly unsuccessful (T1 failed on P1)!")
        print("Originally unsuccessful stats:")
        for v, cnt in og_verdict_df["verdict"].value_counts().items():
            print(f"  {v} -> {round(100*cnt/len(og_verdict_df), 1)}% ({cnt})")

    def detect_repaired_tests(self):
        changed_tests_verdicts_path = self.output_path / "testExecution" / "changed_tests_verdicts.json"
        coverage_path = self.output_path / "testExecution" / "coverage.json"
        repaired_tests_path = self.output_path / "codeMining" / "repaired_tests.json"
        if changed_tests_verdicts_path.exists() and repaired_tests_path.exists() and coverage_path.exists():
            print("Tests have been already executed, skipping ...")
            return json.loads(repaired_tests_path.read_text())

        changed_tests = pd.read_json(self.output_path / "codeMining" / "changed_tests.json")
        if changed_tests.empty:
            print("No Changed Tests Found!")
            return []

        change_groups = list(changed_tests.groupby("aCommit"))
        changed_tests_cnt = sum([len(g[1]) for g in change_groups])

        ghapi.cleanup_worktrees(self.repo_name)

        changed_tests_verdicts = []
        repaired_tests = []
        tests_coverage = []

        proc_cnt = round(mp.cpu_count() / 3) if mp.cpu_count() > 2 else 1
        proc_cnt = min(proc_cnt, len(change_groups))
        with mp.Pool(proc_cnt, initializer=pool_init, initargs=(mp.Lock(),)) as pool:
            for verdicts, repaired, test_coverage in tqdm(
                pool.imap_unordered(self.run_changed_tests, change_groups),
                total=len(change_groups),
                ascii=True,
                desc="Executing tests",
            ):
                changed_tests_verdicts.extend(verdicts)
                repaired_tests.extend(repaired)
                tests_coverage.extend(test_coverage)

        ghapi.cleanup_worktrees(self.repo_name)

        coverage = {}
        for test_coverage in tests_coverage:
            b_commit, test_name, covered_lines = test_coverage
            coverage.setdefault(b_commit, {})
            coverage[b_commit].setdefault(test_name, {})
            coverage[b_commit][test_name] = covered_lines

        changed_tests_verdicts_path.parent.mkdir(exist_ok=True, parents=True)
        changed_tests_verdicts_path.write_text(json.dumps(changed_tests_verdicts, indent=2, sort_keys=False))
        coverage_path.write_text(json.dumps(coverage, indent=2, sort_keys=False))
        repaired_tests_path.write_text(json.dumps(repaired_tests, indent=2, sort_keys=False))
        self.print_execution_stats(changed_tests_verdicts, repaired_tests, changed_tests_cnt)
        return repaired_tests

    def find_changed_sut_classes(self, commits):
        changed_sut_classes_path = self.output_path / "codeMining" / "changed_sut_classes.json"
        if changed_sut_classes_path.exists():
            print("Changed SUT classes already exists, skipping ...")
            return

        repo = ghapi.get_repo(self.repo_name)
        changed_classes = []
        for b_commit, a_commit in tqdm(commits, ascii=True, desc="Finding changed classes in the SUT"):
            diffs = get_java_diffs(repo.commit(a_commit))
            commit_changed_classes = []
            for diff in diffs:
                commit_changed_classes.append((diff.b_path, diff.a_path))
            changed_classes.append({"bCommit": b_commit, "aCommit": a_commit, "changedClasses": commit_changed_classes})

        changed_sut_classes_path.write_text(json.dumps(changed_classes, indent=2, sort_keys=False))

    def label_changed_test_sources(self):
        print("Labeling changed test sources...")
        sut_class_changes_path = self.output_path / "codeMining" / "sut_class_changes.json"
        sut_method_changes_path = self.output_path / "codeMining" / "sut_method_changes.json"
        changed_test_classes_path = self.output_path / "codeMining" / "changed_test_classes.csv"

        changed_test_classes = pd.read_csv(changed_test_classes_path)
        test_classes = set(changed_test_classes["b_path"].values.tolist() + changed_test_classes["a_path"].values.tolist())

        def is_test_source(b_path, a_path):
            is_test_source = False
            if b_path in test_classes or a_path in test_classes:
                is_test_source = True
            elif "src/test" in b_path or "src/test" in a_path:
                is_test_source = True
            return is_test_source

        sut_class_changes = json.loads(sut_class_changes_path.read_text())
        for commit_changes in sut_class_changes:
            for file_changes in commit_changes["changes"]:
                file_changes["is_test_source"] = is_test_source(file_changes["bPath"], file_changes["aPath"])
        sut_class_changes_path.write_text(json.dumps(sut_class_changes, indent=2, sort_keys=False))

        sut_method_changes = json.loads(sut_method_changes_path.read_text())
        for commit_changes in sut_method_changes:
            for file_changes in commit_changes["changes"]:
                file_changes["is_test_source"] = is_test_source(file_changes["bPath"], file_changes["aPath"])
        sut_method_changes_path.write_text(json.dumps(sut_method_changes, indent=2, sort_keys=False))

    def make_dataset(self, repaired_tests):
        method_change_repo = MethodChangesRepository(self.output_path)
        trivial_detector = TrivialDetector(self.output_path)
        dup_cnt = 0
        dataset = {}
        for i, repair in tqdm(enumerate(repaired_tests), total=len(repaired_tests), ascii=True, desc="Creating dataset"):
            _repair = copy.deepcopy(repair)

            _repair["aCommitTime"] = ghapi.get_commit_time(_repair["aCommit"], self.repo_name)
            _repair["ID"] = f"{self.repo_name}:{i}"
            _repair["trivial"] = trivial_detector.detect_trivial_repair(
                _repair["name"], _repair["aCommit"], _repair["bCommit"]
            )
            _repair["hunk"] = method_change_repo.get_test_hunk(_repair)
            repair_key = (
                _repair["name"]
                + "||"
                + _repair["bPath"]
                + "||"
                + _repair["bSource"]["code"]
                + "||"
                + hunk_to_string(_repair["hunk"])
            )
            if repair_key in dataset:
                dup_cnt += 1
            if repair_key not in dataset or dataset[repair_key]["aCommitTime"] < _repair["aCommitTime"]:
                dataset[repair_key] = _repair

        dup_per = round(100 * dup_cnt / len(repaired_tests), 1)
        print(f"Removed {dup_per}% ({dup_cnt} / {len(repaired_tests)}) duplicate repairs.")

        dataset_l = list(dataset.values())
        dataset_l.sort(key=lambda r: r["aCommitTime"], reverse=True)
        (self.output_path / "dataset.json").write_text(json.dumps(dataset_l, indent=2, sort_keys=False))
        print(f"Done! Saved {len(dataset)} test repairs.")


class CEPROTDataCollector(DataCollector):
    def __init__(self, repo_name, output_path, ceprot_path):
        self.repo_name = repo_name
        self.output_path = Path(output_path)
        ceprot_df = pd.read_csv(ceprot_path)
        self.cerport_df = ceprot_df[ceprot_df["project"] == self.repo_name].reset_index(drop=True)
        try:
            ghapi.get_repo(repo_name)
        except:
            (self.output_path / "missing_repo.csv").open("a").write(repo_name + "\n")
            print(f"Repo missing from GitHub")
            sys.exit()

    def detect_repaired_tests(self):
        changed_tests = pd.read_json(self.output_path / "codeMining" / "changed_tests.json")
        if changed_tests.empty:
            print("No Changed Tests Found!")
            return []

        changed_tests["test_method_name"] = changed_tests["name"].apply(lambda n: n.split(".")[-1].replace("()", ""))
        repaired_tests = pd.merge(
            self.cerport_df,
            changed_tests,
            how="left",
            left_on=["commit", "path", "tgt_name"],
            right_on=["aCommit", "aPath", "test_method_name"],
        )
        repaired_tests = repaired_tests[repaired_tests["status"] == "OK"].reset_index(drop=True)
        print(f"Matched {len(repaired_tests)} repaired tests with CEPROT")
        repaired_tests.rename(columns={"id": "CID"}, inplace=True)
        hunk_col = []
        for _, row in repaired_tests.iterrows():
            if len(row["hunks"]) > 1:
                print(f"Multi hunks found: {row['id']}")
            hunk_col.append(row["hunks"][0])
        repaired_tests["hunk"] = hunk_col
        repaired_tests.drop(
            columns=["commit", "path", "src_name", "tgt_name", "eq_src_tgt", "test_method_name", "hunks"], inplace=True
        )
        repaired_tests.to_json(self.output_path / "codeMining" / "repaired_tests.json", orient="records", indent=2)
        return repaired_tests.to_dict(orient="records")

    def make_dataset(self, repaired_tests):
        method_change_repo = MethodChangesRepository(self.output_path)
        trivial_detector = TrivialDetector(self.output_path)
        dataset_l = []
        for i, repair in tqdm(enumerate(repaired_tests), total=len(repaired_tests), ascii=True, desc="Creating dataset"):
            _repair = copy.deepcopy(repair)
            _repair = {
                "ID": f"{self.repo_name}:{i}",
                "CID": _repair["CID"],
                "project": _repair["project"],
                "aCommit": _repair["aCommit"],
                "aCommitTime": ghapi.get_commit_time(_repair["aCommit"], self.repo_name),
                "bCommit": _repair["bCommit"],
                "aPath": _repair["aPath"],
                "bPath": _repair["bPath"],
                "name": _repair["name"],
                "status": _repair["status"],
                "hunk": method_change_repo.get_test_hunk(_repair),
                **_repair,
                "trivial": trivial_detector.detect_trivial_repair(_repair["name"], _repair["aCommit"], _repair["bCommit"]),
            }
            dataset_l.append(_repair)

        dataset_l.sort(key=lambda r: r["aCommitTime"], reverse=True)
        (self.output_path / "dataset.json").write_text(json.dumps(dataset_l, indent=2, sort_keys=False))
        print(f"Done! Saved {len(dataset_l)} test repairs.")

    def collect_test_repairs(self):
        print(f"Phase #1: Identifying changed tests and extracting their changes: {self.repo_name}")
        self.identify_changed_test_classes()
        jparser.compare_test_classes(self.output_path)
        print()

        print("Phase #2: Matching changed_test.json with CEPROT's test db")
        repaired_tests = self.detect_repaired_tests()
        if len(repaired_tests) == 0:
            print("No repaired tests found")
            return
        print()

        print("Phase #3: Identifying and extracting covered changes")
        repair_commits = set([(r["bCommit"], r["aCommit"]) for r in repaired_tests])
        self.find_changed_sut_classes(repair_commits)
        jparser.extract_covered_changes_info(self.output_path)
        self.label_changed_test_sources()
        ghapi.cleanup_worktrees(self.repo_name)
        print()

        self.make_dataset(repaired_tests)

        ErrorStats.report()

    def identify_changed_test_classes(self):
        changed_test_classes_path = self.output_path / "codeMining" / "changed_test_classes.csv"
        if changed_test_classes_path.exists():
            print("Changed tests classes already exists, skipping ...")
            return

        commits_sha = self.cerport_df["commit"].values.tolist()

        changed_test_classes = []
        with mp.Pool(initializer=pool_init, initargs=(mp.Lock(),)) as pool:
            for commit_changed_test_classes in tqdm(
                pool.imap_unordered(self.get_commit_changed_test_classes, commits_sha),
                total=len(commits_sha),
                ascii=True,
                desc="Identifying changed test classes",
            ):
                changed_test_classes.extend(commit_changed_test_classes)

        changed_test_classes = pd.DataFrame(changed_test_classes)
        if len(changed_test_classes) > 0:
            changed_test_classes = changed_test_classes[
                changed_test_classes["b_path"].isin(self.cerport_df["path"].values.tolist())
            ]
        changed_test_classes.to_csv(changed_test_classes_path, index=False)
