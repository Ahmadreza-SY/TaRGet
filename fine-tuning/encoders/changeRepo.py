from encoders.preprocessing.commentRemoval import remove_empty_hunks
from encoders.preprocessing.textDiff import remove_whitespace_hunks
from encoders.preprocessing.codeFormatter import format_sut_changes
from encoders.preprocessing.utils import get_hunk_location
from pathlib import Path
import json
import logging


class ChangeRepository:
    def __init__(self, args):
        self.changes_cache = {}
        self.stats = {"empty_chn": {}, "hunk_pp": {}, "hunks": 0}
        self.args = args
        self.logger = logging.getLogger("MAIN")

    def log(self, msg):
        self.logger.info(msg)

    def get_commit_changes(self, project, a_commit):
        key = f"{project}/{a_commit}"
        if key in self.changes_cache:
            return self.changes_cache[key]

        project_changes_cache = self.get_project_changes(project)
        self.changes_cache.update(project_changes_cache)

        if key not in self.changes_cache:
            self.stats["empty_chn"][key] = "Not Found"
            self.changes_cache[key] = []

        return self.changes_cache[key]

    def read_changes(self, project, change_type):
        ds_path = Path(self.args.dataset_dir)
        if project not in self.args.dataset_dir:
            ds_path = ds_path / project
        changes_path = list(ds_path.rglob(f"sut_{change_type}_changes.json"))
        changes = []
        if len(changes_path) == 1:
            changes = json.loads(changes_path[0].read_text())
        return changes

    def get_project_changes(self, project):
        method_changes = self.read_changes(project, "method")
        class_changes = self.read_changes(project, "class")
        for class_commit_changes in class_changes:
            for method_commit_changes in method_changes:
                if method_commit_changes["aCommit"] == class_commit_changes["aCommit"]:
                    self.label_hunks(class_commit_changes, method_commit_changes)
                    break
        project_changes = {}
        for commit_changes in class_changes:
            commit_changes_wo_t = [c for c in commit_changes["changes"] if not c["is_test_source"]]
            commit_changes_pp = self.preprocess_changes(commit_changes_wo_t)
            current_key = f"{project}/{commit_changes['aCommit']}"
            project_changes[current_key] = commit_changes_pp
            self.stats["hunks"] += self.hunks_count(commit_changes_pp)
            if len(commit_changes_pp) == 0:
                self.stats["empty_chn"][current_key] = self.get_empty_changes_reason(
                    commit_changes["changes"], commit_changes_wo_t, commit_changes_pp
                )
        return project_changes

    def preprocess_changes(self, changes):
        preprocessors = [
            format_sut_changes,
            remove_whitespace_hunks,
            remove_empty_hunks,
        ]
        for preprocess in preprocessors:
            b_len = self.hunks_count(changes)
            changes = preprocess(changes)
            a_len = self.hunks_count(changes)
            self.stats["hunk_pp"][preprocess.__name__] = self.stats["hunk_pp"].get(preprocess.__name__, 0) + (b_len - a_len)
        return changes

    def hunks_count(self, changes):
        return sum(len(c["hunks"]) for c in changes)

    def label_hunks(self, class_changes, method_changes):
        for c_change in class_changes["changes"]:
            m_hunks = {}
            for m_change in method_changes["changes"]:
                if c_change["bPath"] != m_change["bPath"] or len(m_change["hunks"]) == 0:
                    continue
                for m_hunk in m_change["hunks"]:
                    m_hunks[get_hunk_location(m_hunk)] = m_change["name"]

            for c_hunk in c_change["hunks"]:
                c_hunk["scope"] = "class"
                c_hunk_loc = get_hunk_location(c_hunk)
                if c_hunk_loc in m_hunks:
                    c_hunk["scope"] = "method"
                    c_hunk["methodName"] = m_hunks[c_hunk_loc]

    def get_empty_changes_reason(self, changes, changes_wo_t, changes_pp):
        if len(changes) == 0:
            return "Originally Empty"
        elif len(changes_wo_t) == 0:
            return "All Test Source"
        elif len(changes_pp) == 0:
            if len(changes_wo_t) == len(changes):
                return "Preproccessing"
            else:
                return "Combination of Both"

    def log_stats(self, ds):
        # Empty change stats
        stats_cnt = {}
        empty_chn = self.stats["empty_chn"]
        for _, row in ds.iterrows():
            key = f"{row['project']}/{row['aCommit']}"
            if key in empty_chn:
                reason = empty_chn[key]
                stats_cnt.setdefault(reason, 0)
                stats_cnt[reason] += 1
        for k, v in stats_cnt.items():
            self.log(f"Got {v} empty changes due to {k}")

        # Hunks preprocessing stats
        total_hunks = self.stats["hunks"] + sum(self.stats["hunk_pp"].values())
        for k, v in self.stats["hunk_pp"].items():
            if v > 0:
                self.log(f"{k} removed {v} ({round(100*v/total_hunks, 1)}%) hunks from SUT changes")
                total_hunks -= v
        self.log(f"Total SUT hunks after preprocessing: {total_hunks}")
