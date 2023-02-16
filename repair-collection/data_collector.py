from pathlib import Path
import pandas as pd
import git_api as ghapi
from tqdm import tqdm
import json
import copy
from utils import save_file, is_test_class, get_java_diffs, no_covered_changes, hunk_to_string, get_hunk_lines
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

    def get_commit_changed_test_classes(self, commit_sha):
        commit = ghapi.get_commit(commit_sha, self.repo_name)
        if len(commit.parents) == 0:
            return []

        commit_changed_test_classes = []
        diffs = get_java_diffs(commit)
        for diff in diffs:
            before, after = ghapi.get_file_versions(diff, commit, self.repo_name)
            if is_test_class(before) and before != after:
                b_commit = ghapi.get_short_commit(commit.parents[0], self.repo_name)
                a_commit = ghapi.get_short_commit(commit, self.repo_name)
                commit_changed_test_classes.append(
                    {"b_path": diff.b_path, "a_path": diff.a_path, "b_commit": b_commit, "a_commit": a_commit}
                )
                b_copy_path = self.output_path / "testClasses" / b_commit / diff.b_path
                a_copy_path = self.output_path / "testClasses" / a_commit / diff.a_path
                save_file(before, b_copy_path)
                save_file(after, a_copy_path)

        return commit_changed_test_classes

    def identify_changed_test_classes(self):
        changed_test_classes_path = self.output_path / "changed_test_classes.csv"
        if changed_test_classes_path.exists():
            print("Changed tests classes already exists, skipping ...")
            return
        commits = ghapi.get_all_commits(self.repo_name)
        commits_sha = [c.hexsha for c in commits]

        changed_test_classes = []
        with mp.Pool() as pool:
            for commit_changed_test_classes in tqdm(
                pool.imap_unordered(self.get_commit_changed_test_classes, commits_sha),
                total=len(commits_sha),
                ascii=True,
                desc="Identifying changed test classes",
            ):
                changed_test_classes.extend(commit_changed_test_classes)

        changed_test_classes = pd.DataFrame(changed_test_classes)
        changed_test_classes.to_csv(changed_test_classes_path, index=False)

    def run_changed_tests(self, change_group):
        changed_tests_verdicts = []
        repaired_tests = []
        (a_commit, changes) = change_group

        lock.acquire()
        a_commit_path = ghapi.copy_commit_code(self.repo_name, a_commit, "0")
        lock.release()

        for _, change in changes.iterrows():
            test_simple_name = change["name"].split(".")[-1].replace("()", "")
            test_a_path = Path(change["aPath"])
            original_file = self.output_path / "testClasses" / a_commit / test_a_path
            broken_file = self.output_path / "brokenPatches" / a_commit / original_file.stem / test_simple_name / test_a_path
            log_path = Path(a_commit) / original_file.stem / test_simple_name / test_a_path.parent
            broken_log_path = self.output_path / "brokenExeLogs" / log_path
            executable_file = a_commit_path / test_a_path
            shutil.copyfile(str(broken_file), str(executable_file))
            # To detect whether the test case is broken (needs repair)
            before_verdict = mvnp.compile_and_run_test(a_commit_path, test_a_path, test_simple_name, broken_log_path)
            shutil.copyfile(str(original_file), str(executable_file))

            after_verdict = None
            repaired_log_path = self.output_path / "repairedExeLogs" / log_path
            if before_verdict.is_broken():
                # To detect whether test case is correctly repaired
                after_verdict = mvnp.compile_and_run_test(a_commit_path, test_a_path, test_simple_name, repaired_log_path)
                if after_verdict.succeeded():
                    change_obj = change.to_dict()
                    change_obj["verdict"] = before_verdict.to_dict()
                    repaired_tests.append(change_obj)

            changed_tests_verdicts.append(
                {
                    "name": change["name"],
                    "aCommit": change["aCommit"],
                    "verdict": before_verdict.to_dict(),
                    "broken": before_verdict.is_broken(),
                    "correctly_repaired": after_verdict.succeeded() if after_verdict is not None else None,
                }
            )

        lock.acquire()
        ghapi.remove_commit_code(self.repo_name, a_commit_path)
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

        proc_cnt = round(mp.cpu_count() / 4) if mp.cpu_count() > 2 else 1
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
        print(f"Executed {changed_tests_cnt} test cases!")

        verdict_df = pd.DataFrame(
            {
                "verdict": [v["verdict"]["status"] for v in changed_tests_verdicts],
                "correctly_repaired": [v["correctly_repaired"] for v in changed_tests_verdicts],
            }
        )
        print("Verdict stats:")
        for v, cnt in verdict_df["verdict"].value_counts().items():
            print(f"  {v} -> {round(100*cnt/len(verdict_df), 1)}% ({cnt})")

        print("Correctly repaired stats:")
        for v, cnt in verdict_df["correctly_repaired"].value_counts(dropna=False).items():
            print(f"  {v} -> {round(100*cnt/len(verdict_df), 1)}% ({cnt})")

        repair_per = round(100 * len(repaired_tests) / changed_tests_cnt, 1)
        print(
            f"{repair_per}% ({len(repaired_tests)}/{changed_tests_cnt}) of changed tests were broken and correclty repaired!"
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
            diffs = get_java_diffs(repo.commit(a_commit))
            commit_changed_classes = []
            for diff in diffs:
                if diff.a_path in changed_test_class_paths or diff.b_path in changed_test_class_paths:
                    continue
                commit_changed_classes.append((diff.b_path, diff.a_path))
            changed_classes.append({"bCommit": b_commit, "aCommit": a_commit, "changedClasses": commit_changed_classes})

        changed_sut_classes_path.write_text(json.dumps(changed_classes, indent=2, sort_keys=False))

    def remove_common_hunks(self, repair):
        covered_class_changes = repair["coveredClassChanges"]
        covered_method_changes = repair["coveredMethodChanges"]
        if len(covered_method_changes) == 0:
            return

        result = []
        for class_change in covered_class_changes:
            common_hunks_i = set()
            for method_change in covered_method_changes:
                if class_change["filePath"] != method_change["filePath"]:
                    continue
                method_lines = [get_hunk_lines(h) for h in method_change["hunks"]]
                method_source_lines = set.union(*[l[0] for l in method_lines])
                method_target_lines = set.union(*[l[1] for l in method_lines])
                class_hunk_lines = [get_hunk_lines(h) for h in class_change["hunks"]]
                for i, lines in enumerate(class_hunk_lines):
                    if (
                        len(lines[0].intersection(method_source_lines)) > 0
                        or len(lines[1].intersection(method_target_lines)) > 0
                    ):
                        common_hunks_i.add(i)

            uncommon_hunks = [h for i, h in enumerate(class_change["hunks"]) if i not in common_hunks_i]
            if len(uncommon_hunks) > 0:
                class_change["hunks"] = uncommon_hunks
                result.append(class_change)

        repair["coveredClassChanges"] = result

    def make_dataset(self, repaired_tests):
        class_change_repo = ClassChangesRepository(self.output_path)
        method_change_repo = MethodChangesRepository(self.output_path)
        zero_cov_cnt = 0
        dup_cnt = 0
        dataset = {}
        for i, repair in tqdm(enumerate(repaired_tests), total=len(repaired_tests), ascii=True, desc="Creating dataset"):
            _repair = copy.deepcopy(repair)

            covered_class_changes = class_change_repo.get_covered_changes(_repair)
            covered_method_changes = method_change_repo.get_covered_changes(_repair)
            _repair["coveredClassChanges"] = covered_class_changes
            _repair["coveredMethodChanges"] = covered_method_changes
            self.remove_common_hunks(_repair)
            if no_covered_changes(_repair):
                zero_cov_cnt += 1
                continue

            _repair["aCommitTime"] = ghapi.get_commit_time(_repair["aCommit"], self.repo_name)
            _repair["ID"] = f"{self.repo_name}:{i}"
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

        zero_cov_per = round(100 * zero_cov_cnt / len(repaired_tests), 1)
        print(f"Removed {zero_cov_per}% ({zero_cov_cnt} / {len(repaired_tests)}) repairs due to zero coverage.")
        dup_per = round(100 * dup_cnt / len(repaired_tests), 1)
        print(f"Removed {dup_per}% ({dup_cnt} / {len(repaired_tests)}) duplicate repairs.")

        dataset_l = list(dataset.values())
        dataset_l.sort(key=lambda r: r["aCommitTime"], reverse=True)
        (self.output_path / "dataset.json").write_text(json.dumps(dataset_l, indent=2, sort_keys=False))
        print(f"Done! Saved {len(dataset)} test repairs.")
