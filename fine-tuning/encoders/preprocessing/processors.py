from encoders.preprocessing.commentRemoval import (
    remove_hunk_comments,
    hunk_is_empty,
)
from encoders.preprocessing.codeFormatter import format_hunk, format_covered_changes, format_source
from encoders.preprocessing.textDiff import get_hunk_diffs
from diff_match_patch import diff_match_patch as dmp


class Processors:
    @staticmethod
    def remove_repair_comments(ds):
        ds["hunk"] = ds["hunk"].apply(lambda h: remove_hunk_comments(h))
        ds["hunk_is_empty"] = ds["hunk"].apply(lambda h: hunk_is_empty(h))
        ds = ds[~ds["hunk_is_empty"]].reset_index(drop=True).drop(columns=["hunk_is_empty"])
        return ds

    @staticmethod
    def format_code(ds):
        ds["hunk"] = ds["hunk"].apply(lambda h: format_hunk(h))
        ds["coveredClassChanges"] = ds["coveredClassChanges"].apply(lambda c: format_covered_changes(c))
        ds["coveredMethodChanges"] = ds["coveredMethodChanges"].apply(lambda m: format_covered_changes(m))
        ds["aSource"] = ds["aSource"].apply(lambda s: format_source(s))
        ds["bSource"] = ds["bSource"].apply(lambda s: format_source(s))
        return ds

    @staticmethod
    def remove_whitespace_hunks(ds):
        def _remove_whitespace_hunks(covered_changes):
            for c in covered_changes:
                hunks = []
                for h in c["hunks"]:
                    diffs = get_hunk_diffs(h)
                    change_cnt = sum([1 for type, _ in diffs if type in [dmp.DIFF_INSERT, dmp.DIFF_DELETE]])
                    if change_cnt > 0:
                        hunks.append(h)
                c["hunks"] = hunks
            covered_changes = [c for c in covered_changes if len(c["hunks"]) > 0]
            return covered_changes

        ds["coveredClassChanges"] = ds["coveredClassChanges"].apply(lambda c: _remove_whitespace_hunks(c))
        ds["coveredMethodChanges"] = ds["coveredMethodChanges"].apply(lambda m: _remove_whitespace_hunks(m))
        return ds

    @staticmethod
    def remove_empty_hunks(ds):
        def _remove_empty_hunks(covered_changes):
            for c in covered_changes:
                c["hunks"] = [h for h in c["hunks"] if not hunk_is_empty(h)]
            covered_changes = [c for c in covered_changes if len(c["hunks"]) > 0]
            return covered_changes

        ds["coveredClassChanges"] = ds["coveredClassChanges"].apply(lambda c: _remove_empty_hunks(c))
        ds["coveredMethodChanges"] = ds["coveredMethodChanges"].apply(lambda m: _remove_empty_hunks(m))
        return ds

    @staticmethod
    def remove_empty_covered_changes(ds):
        ds["cov_is_empty"] = ds.apply(
            lambda r: len(r["coveredClassChanges"]) == 0 and len(r["coveredMethodChanges"]) == 0, axis=1
        )
        ds = ds[~ds["cov_is_empty"]].reset_index(drop=True).drop(columns=["cov_is_empty"])
        return ds

    @staticmethod
    def remove_no_source_changes(ds):
        ds["has_source_changes"] = ds["hunk"].apply(lambda h: "sourceChanges" in h and len(h["sourceChanges"]) > 0)
        ds = ds[ds["has_source_changes"]].reset_index(drop=True).drop(columns=["has_source_changes"])
        return ds

    @staticmethod
    def remove_trivial_repairs(ds):
        ds = ds[ds["trivial"].isna()].reset_index(drop=True)
        return ds
