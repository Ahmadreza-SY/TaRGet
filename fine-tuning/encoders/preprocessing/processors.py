from encoders.preprocessing.commentRemoval import remove_hunk_comments, hunk_is_empty, _remove_empty_hunks
from encoders.preprocessing.codeFormatter import format_hunk, format_sut_changes
from encoders.preprocessing.textDiff import _remove_whitespace_hunks
from joblib import Parallel, delayed


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
        ds["coveredClassChanges"] = Parallel(n_jobs=-1)(delayed(format_sut_changes)(c) for c in ds["coveredClassChanges"])
        ds["coveredMethodChanges"] = Parallel(n_jobs=-1)(delayed(format_sut_changes)(c) for c in ds["coveredMethodChanges"])
        return ds

    @staticmethod
    def remove_whitespace_hunks(ds):
        ds["coveredClassChanges"] = Parallel(n_jobs=-1)(
            delayed(_remove_whitespace_hunks)(c) for c in ds["coveredClassChanges"]
        )
        ds["coveredMethodChanges"] = Parallel(n_jobs=-1)(
            delayed(_remove_whitespace_hunks)(c) for c in ds["coveredMethodChanges"]
        )
        return ds

    @staticmethod
    def remove_empty_hunks(ds):
        ds["coveredClassChanges"] = Parallel(n_jobs=-1)(delayed(_remove_empty_hunks)(c) for c in ds["coveredClassChanges"])
        ds["coveredMethodChanges"] = Parallel(n_jobs=-1)(delayed(_remove_empty_hunks)(c) for c in ds["coveredMethodChanges"])
        return ds

    @staticmethod
    def remove_empty_changes(ds):
        ds["cov_is_empty"] = ds.apply(
            lambda r: len(r["coveredClassChanges"]) == 0
            and len(r["allClassChanges"]) == 0
            and len(r["coveredMethodChanges"]) == 0,
            axis=1,
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

    @staticmethod
    def remove_empty_prioritized_changes(ds):
        ds = ds[ds["prioritized_changes"].map(len) > 0].reset_index(drop=True)
        return ds
