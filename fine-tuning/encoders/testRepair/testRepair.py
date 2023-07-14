import pandas as pd
import numpy as np
from pathlib import Path
from encoders.encoders import BaseDataEncoder
from encoders.testRepair.code_white_space_formatter import format_hunk, format_covered_changes, format_source


class Tokens:
    BREAKAGE = "<breakage>"
    TEST_CONTEXT = "<testContext>"
    COVERED_CONTEXT = "<coveredContext>"
    DELETE = "<del>"
    ADD = "<add>"
    HUNK = "<hunk>"


class TestRepairDataEncoder(BaseDataEncoder):
    def __init__(self, args):
        super().__init__(args)
        self.tokenizer.add_tokens(
            [Tokens.BREAKAGE, Tokens.TEST_CONTEXT, Tokens.COVERED_CONTEXT, Tokens.DELETE, Tokens.ADD, Tokens.HUNK]
        )

    def shuffle(self, ds):
        return ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True)

    def split_by_tag(self, ds):
        projects = ds["project"].unique().tolist()
        train_ds_list, valid_ds_list, test_ds_list = [], [], []
        for project in projects:
            project_ds = ds[ds["project"] == project].sort_values("aCommitTime").reset_index(drop=True)

            dup_ind = project_ds[~project_ds["aCommit"].duplicated()].index.tolist()[1:]
            train_size = int(self.args.train_size * len(project_ds))
            train_dup_ind = [i for i in dup_ind if i <= (train_size - 1)]
            if len(train_dup_ind) == 0:
                train_split_i = dup_ind[0]
            else:
                train_split_i = train_dup_ind[-1]
            p_train_ds, p_eval_ds = np.split(project_ds, [train_split_i])

            # stratified test and valid split
            p_eval_ds = self.shuffle(p_eval_ds)
            p_eval_list = [np.split(g, [int(0.5 * len(g))]) for _, g in p_eval_ds.groupby("aCommit")]
            p_valid_ds = pd.concat([t[0] for t in p_eval_list])
            p_test_ds = pd.concat([t[1] for t in p_eval_list])

            train_ds_list.append(p_train_ds)
            valid_ds_list.append(p_valid_ds)
            test_ds_list.append(p_test_ds)

        train_ds = pd.concat(train_ds_list)
        valid_ds = pd.concat(valid_ds_list)
        test_ds = pd.concat(test_ds_list)

        # Shuffle splits
        train_ds = self.shuffle(train_ds)
        valid_ds = self.shuffle(valid_ds)
        test_ds = self.shuffle(test_ds)

        return train_ds, valid_ds, test_ds

    def create_inputs_and_outputs(self, ds):
        pass

    def preprocess(self, ds):
        ds['hunk'] = ds['hunk'].apply(lambda h : format_hunk(h))
        ds['coveredClassChanges'] = ds['coveredClassChanges'].apply(lambda c : format_covered_changes(c))
        ds['coveredMethodChanges'] = ds['coveredMethodChanges'].apply(lambda m : format_covered_changes(m))
        ds['aSource'] = ds['aSource'].apply(lambda s : format_source(s))
        ds['bSource'] = ds['bSource'].apply(lambda s : format_source(s))
        return ds
    
    def filter(self, ds):
        before_len = len(ds)
        ds["has_source_changes"] = ds["hunk"].apply(lambda h: "sourceChanges" in h and len(h["sourceChanges"]) > 0)
        ds = ds[ds["has_source_changes"]].reset_index(drop=True).drop(columns=["has_source_changes"])
        self.log(f"Filtered {before_len - len(ds)} rows due to no source changes")

        before_len = len(ds)
        ds = ds[ds["trivial"].isna()].reset_index(drop=True)
        self.log(f"Filtered {before_len - len(ds)} trivial test repairs")

        return ds

    def prepare_inputs_and_outputs(self, ds):
        ds = self.create_inputs_and_outputs(ds)
        ds["input"] = ds["input"].str.strip()
        ds["output"] = ds["output"].str.strip()
        validsize_ind = self.get_validsize_indices(ds)
        return ds.iloc[list(validsize_ind)].reset_index(drop=True)

    def merge_train_with_trivial(self, train_ds, trivial_ds):
        projects = trivial_ds["project"].unique().tolist()
        train_trivial_ds_list = []
        for project in projects:
            latest_train_time = train_ds[train_ds["project"] == project]["aCommitTime"].max()
            project_trivial_ds = trivial_ds[trivial_ds["project"] == project].reset_index(drop=True)
            project_train_trivial_ds = project_trivial_ds[
                project_trivial_ds["aCommitTime"] <= latest_train_time
            ].reset_index(drop=True)
            if len(project_train_trivial_ds) > 0:
                train_trivial_ds_list.append(project_train_trivial_ds)

        train_trivial_ds = None
        if len(train_trivial_ds_list) > 0:
            train_trivial_ds = pd.concat(train_trivial_ds_list)

        if train_trivial_ds is None or len(train_trivial_ds) == 0:
            self.log("No trivial repairs to add to train")
        else:
            self.log("Preparing trivial train dataset")
            train_trivial_ds = self.prepare_inputs_and_outputs(train_trivial_ds)
            train_ds = pd.concat([train_ds, train_trivial_ds])
            train_ds = self.shuffle(train_ds)
            self.log(f"Added {len(train_trivial_ds)} trivial test repairs to the train set")

        return train_ds

    def read_and_preproces(self):
        ds_path = Path(self.args.dataset_dir)
        ds_list = []
        for project_ds_path in ds_path.rglob("dataset.json"):
            project_ds = pd.read_json(project_ds_path)
            project_ds["project"] = f"{project_ds_path.parent.parent.name}/{project_ds_path.parent.name}"
            project_ds = self.preprocess(project_ds)
            if len(project_ds) == 0:
                continue
            ds_list.append(project_ds)

        if len(ds_list) == 0:
            raise Exception(f"No datasets found in {ds_path}")
        ds = pd.concat(ds_list)
        self.log(f"Read and preprocessed {len(ds)} samples from {len(ds_list)} projects")

        return ds

    def load_dataset(self):
        self.log("Loading test repair datasets ...")

        ds_output_dir = self.args.output_dir / "splits"
        train_file = ds_output_dir / "train.json"
        valid_file = ds_output_dir / "valid.json"
        test_file = ds_output_dir / "test.json"

        if train_file.exists() and valid_file.exists() and test_file.exists():
            self.log("Loading train, valid, and test splits from disk ...")
            train_ds = pd.read_json(train_file)
            valid_ds = pd.read_json(valid_file)
            test_ds = pd.read_json(test_file)
        else:
            ds = self.read_and_preproces()
            trivial_ds = ds[~ds["trivial"].isna()].reset_index(drop=True)
            ds = self.filter(ds)

            self.log("Preparing main dataset")
            ds = self.prepare_inputs_and_outputs(ds)

            train_ds, valid_ds, test_ds = self.split_by_tag(ds)

            train_ds = self.merge_train_with_trivial(train_ds, trivial_ds)

            ds_output_dir.mkdir(exist_ok=True, parents=True)
            train_ds.to_json(train_file, orient="records", indent=2)
            valid_ds.to_json(valid_file, orient="records", indent=2)
            test_ds.to_json(test_file, orient="records", indent=2)

        if self.args.sub_sample:
            ratio = self.args.sample_ratio
            self.log(f"Subsampling with ration {ratio}")
            # Warning: sub sampling is not stratified by ID
            train_ds = train_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True)
            valid_ds = valid_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True)
            test_ds = test_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True)

        ds_len = len(train_ds) + len(valid_ds) + len(test_ds)
        self.log(f"Train: {len(train_ds)} ({round(100 * len(train_ds) / ds_len, 1)} %)")
        self.log(f"Valid: {len(valid_ds)} ({round(100 * len(valid_ds) / ds_len, 1)} %)")
        self.log(f"Test: {len(test_ds)} ({round(100 * len(test_ds) / ds_len, 1)} %)")

        return self.create_tensor_ds(train_ds), self.create_tensor_ds(valid_ds), self.create_tensor_ds(test_ds)
