import pandas as pd
import numpy as np
from pathlib import Path
from encoders.encoders import BaseDataEncoder


class TestRepairDataEncoder(BaseDataEncoder):
    def split_by_tag(self, ds):
        projects = ds["project"].unique().tolist()
        train_ds_list, valid_ds_list, test_ds_list = [], [], []
        for project in projects:
            project_ds = ds[ds["project"] == project].iloc[::-1].reset_index(drop=True)

            dup_ind = project_ds[~project_ds["base_tag"].duplicated()].index.tolist()[1:]
            train_size = int(self.args.train_size * len(project_ds))
            train_dup_ind = [i for i in dup_ind if i <= (train_size - 1)]
            if len(train_dup_ind) == 0:
                train_split_i = dup_ind[0]
            else:
                train_split_i = train_dup_ind[-1]
            p_train_ds, p_eval_ds = np.split(project_ds, [train_split_i])

            # stratified test and valid split
            p_eval_list = [np.split(g, [int(0.5 * len(g))]) for _, g in p_eval_ds.groupby("project")]
            p_valid_ds = pd.concat([t[0] for t in p_eval_list])
            p_test_ds = pd.concat([t[1] for t in p_eval_list])

            train_ds_list.append(p_train_ds)
            valid_ds_list.append(p_valid_ds)
            test_ds_list.append(p_test_ds)

        train_ds = pd.concat(train_ds_list)
        valid_ds = pd.concat(valid_ds_list)
        test_ds = pd.concat(test_ds_list)

        # Shuffle splits
        train_ds = train_ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True)
        valid_ds = valid_ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True)
        test_ds = test_ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True)

        return train_ds, valid_ds, test_ds

    def create_inputs_and_outputs(self, ds):
        pass

    def preprocess(self, ds):
        self.log(f"Preprocessing project {ds.iloc[0]['project']} ( original size {len(ds)} )")
        before_len = len(ds)
        ds = ds[ds["covered_changes"].map(len) > 0].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to zero change coverage.")
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
            ds_path = Path(self.args.dataset_dir)
            ds_list = []
            for project_ds_path in ds_path.rglob("dataset.json"):
                project_ds = pd.read_json(project_ds_path)
                project_ds["project"] = project_ds_path.parent.name
                project_ds["ID"] = [f"{i}:{r['project']}" for i, r in project_ds.iterrows()]
                project_ds = self.preprocess(project_ds)
                if len(project_ds) == 0:
                    continue
                ds_list.append(project_ds)

            ds = pd.concat(ds_list)
            ds = self.create_inputs_and_outputs(ds)
            ds["input"] = ds["input"].str.strip()
            ds["output"] = ds["output"].str.strip()
            validsize_ind = self.get_validsize_indices(ds)
            ds = ds.iloc[list(validsize_ind)].reset_index(drop=True)

            train_ds, valid_ds, test_ds = self.split_by_tag(ds)

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


class BodyDataEncoder(TestRepairDataEncoder):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        ds["before_repair_body"] = ds["before_repair_body"].apply(lambda b: b[1:-1] if b.startswith("{") else b)
        ds["after_repair_body"] = ds["after_repair_body"].apply(lambda b: b[1:-1] if b.startswith("{") else b)
        before_len = len(ds)
        ds = ds[ds["before_repair_body"] != ds["after_repair_body"]].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to same test body before and after repair.")
        return ds
