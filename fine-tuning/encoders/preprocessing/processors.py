from encoders.preprocessing.commentRemoval import remove_hunk_comments, hunk_is_empty
from encoders.preprocessing.codeFormatter import format_hunk
from encoders.preprocessing.textDiff import is_whitespace_hunk
from pathlib import Path
import pandas as pd


class Processors:
    @staticmethod
    def remove_comment_repairs(ds, args):
        ds["hunk"] = ds["hunk"].apply(lambda h: remove_hunk_comments(h))
        ds["hunk_is_empty"] = ds["hunk"].apply(lambda h: hunk_is_empty(h) or is_whitespace_hunk(h))
        ds = ds[~ds["hunk_is_empty"]].drop(columns=["hunk_is_empty"]).reset_index(drop=True)
        return ds

    @staticmethod
    def format_code(ds, args):
        ds["hunk"] = ds["hunk"].apply(lambda h: format_hunk(h))
        return ds

    @staticmethod
    def remove_empty_changes(ds, args):
        ds["chn_is_empty"] = ds.apply(lambda r: len(r["commitChanges"]) == 0, axis=1)
        ds = ds[~ds["chn_is_empty"]].drop(columns=["chn_is_empty"]).reset_index(drop=True)
        return ds

    @staticmethod
    def remove_no_source_changes(ds, args):
        ds["has_source_changes"] = ds["hunk"].apply(lambda h: "sourceChanges" in h and len(h["sourceChanges"]) > 0)
        ds = ds[ds["has_source_changes"]].drop(columns=["has_source_changes"]).reset_index(drop=True)
        return ds

    @staticmethod
    def remove_out_of_range(ds, args):
        def hunk_in_range(row):
            hunk_start = min([l["lineNo"] for l in row["hunk"]["sourceChanges"]])
            hunk_end = max([l["lineNo"] for l in row["hunk"]["sourceChanges"]])
            test_start = row["bSource"]["startLine"]
            test_end = test_start + len(row["bSource"]["code"].split("\n")) - 1
            return test_start <= hunk_start <= test_end and test_start <= hunk_end <= test_end

        ds["in_range"] = ds.apply(hunk_in_range, axis=1)
        ds = ds[ds["in_range"]].drop(columns=["in_range"]).reset_index(drop=True)
        return ds

    @staticmethod
    def remove_oversized_inputs(ds, args):
        os_ids_path = Path(args.dataset_dir) / "oversized_ids.csv"
        if not os_ids_path.exists():
            return ds
        os_ids = pd.read_csv(os_ids_path)["id"].values.tolist()
        ds = ds[~ds["ID"].isin(os_ids)].reset_index(drop=True)
        return ds

    @staticmethod
    def remove_trivial_repairs(ds, args):
        ds = ds[ds["trivial"].isna()].reset_index(drop=True)
        return ds

    @staticmethod
    def remove_empty_prioritized_changes(ds, args):
        ds = ds[ds["prioritized_changes"].map(len) > 0].reset_index(drop=True)
        return ds
