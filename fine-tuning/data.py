import logging
import pandas as pd
import numpy as np
from torch.utils.data import Dataset
from pathlib import Path
from utils import read_lines


class TensorDataset(Dataset):
    def __init__(self, *tensors):
        assert all(tensors[0].shape[0] == tensor.shape[0] for tensor in tensors), "Size mismatch between tensors"
        self.tensors = tensors

    def __getitem__(self, index):
        return tuple(tensor[index] for tensor in self.tensors)

    def __len__(self):
        return self.tensors[0].shape[0]


class BaseDataEncoder:
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(args.pname)
        self.tokenizer = self.args.model_tokenizer_class.from_pretrained(self.args.model_name_or_path)

    def tokenize(self, dataset, return_tensors):
        padding = False
        max_length = None
        if return_tensors is not None:
            padding = "max_length"
            max_length = self.args.max_seq
        model_inputs = self.tokenizer(
            dataset["input"].values.tolist(), return_tensors=return_tensors, padding=padding, max_length=max_length
        )
        model_labels = self.tokenizer(
            text_target=dataset["output"].values.tolist(),
            return_tensors=return_tensors,
            padding=padding,
            max_length=max_length,
        )
        model_inputs["labels"] = model_labels["input_ids"]
        return model_inputs

    def get_validsize_indices(self, dataset):
        model_inputs = self.tokenize(dataset, None)
        validsize_ind = set()
        input_lengths = []
        for i, _ in enumerate(model_inputs["input_ids"]):
            input_lengths.append(len(model_inputs["input_ids"][i]))
            if (
                len(model_inputs["input_ids"][i]) <= self.args.max_seq
                and len(model_inputs["labels"][i]) <= self.args.max_seq
            ):
                validsize_ind.add(i)

        self.logger.info(
            f"The maximum length of inputs is {max(input_lengths)} and the mean is {round(np.mean(input_lengths))}"
        )
        self.logger.info(
            f"{round(100 * len(validsize_ind) / len(dataset), 1)} % ({len(validsize_ind)}/{len(dataset)}) samples had valid length (less that {self.args.max_seq})."
        )

        return validsize_ind

    def create_tensor_ds(self, dataset):
        inputs = self.tokenize(dataset, "pt")
        return TensorDataset(inputs["input_ids"], inputs["attention_mask"], inputs["labels"], dataset["ID"].values)

    def load_dataset(self):
        pass


class ProgramRepairDataEncoder(BaseDataEncoder):
    def read_split(self, split):
        ds_path = Path(self.args.dataset_dir)
        buggy = read_lines(str(ds_path / f"{split}.buggy-fixed.buggy"))
        fixed = read_lines(str(ds_path / f"{split}.buggy-fixed.fixed"))
        ds = pd.DataFrame({"input": buggy, "output": fixed})
        validsize_ind = self.get_validsize_indices(ds)
        ds = ds.iloc[list(validsize_ind)].reset_index(drop=True)
        ds["ID"] = ds.index.tolist()
        if self.args.sub_sample:
            return self.create_tensor_ds(ds.sample(frac=0.15, random_state=self.args.random_seed).reset_index(drop=True))
        return self.create_tensor_ds(ds)

    def load_dataset(self):
        self.logger.info("Loading train ...")
        train_dataset = self.read_split("train")
        self.logger.info("Loading valid ...")
        valid_dataset = self.read_split("valid")
        self.logger.info("Loading test ...")
        test_dataset = self.read_split("test")
        return train_dataset, valid_dataset, test_dataset


class TestRepairDataEncoder(BaseDataEncoder):
    def get_changed_lines(self, row, change_type):
        changed_lines = []
        for change in row["covered_changes"]:
            for hunk in change["hunks"]:
                if "sourceChanges" in hunk:
                    changed_lines.extend(
                        [line_change["line"] for line_change in hunk["sourceChanges"] if line_change["type"] == change_type]
                    )
                if "targetChanges" in hunk:
                    changed_lines.extend(
                        [line_change["line"] for line_change in hunk["targetChanges"] if line_change["type"] == change_type]
                    )
        return changed_lines

    def split_by_release(self, ds):
        projects = ds["project"].unique().tolist()
        train_ds_list, valid_ds_list, test_ds_list = [], [], []
        for project in projects:
            project_ds = ds[ds["project"] == project].iloc[::-1].reset_index(drop=True)

            dup_ind = project_ds[~project_ds["base_release_tag"].duplicated()].index.tolist()[1:]
            train_size = int(self.args.train_size * len(project_ds))
            train_dup_ind = [i for i in dup_ind if i <= (train_size - 1)]
            if len(train_dup_ind) == 0:
                train_split_i = dup_ind[0]
            else:
                train_split_i = train_dup_ind[-1]
            p_train_ds, p_eval_ds = np.split(project_ds, [train_split_i])

            # stratified test and valid split
            p_eval_list = [np.split(g, [int(0.5 * len(g))]) for _, g in p_eval_ds.groupby("ID")]
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

        if self.args.rank == 0:
            self.logger.info(f"Train: {len(train_ds)} ({round(100 * len(train_ds) / len(ds), 1)} %)")
            self.logger.info(f"Valid: {len(valid_ds)} ({round(100 * len(valid_ds) / len(ds), 1)} %)")
            self.logger.info(f"Test: {len(test_ds)} ({round(100 * len(test_ds) / len(ds), 1)} %)")

        if self.args.sub_sample:
            ratio = self.args.sample_ratio
            self.logger.info(f"Subsampling with ration {ratio}")
            # Warning: sub sampling is not stratified by ID
            return (
                train_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True),
                valid_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True),
                test_ds.sample(frac=ratio, random_state=self.args.random_seed).reset_index(drop=True),
            )

        return train_ds, valid_ds, test_ds

    def load_dataset(self):
        self.logger.info("Loading test repair datasets ...")

        ds_path = Path(self.args.dataset_dir)
        ds_list = []
        for project_ds_path in ds_path.glob("*/dataset.json"):
            project_ds = pd.read_json(project_ds_path)
            project_ds["project"] = project_ds_path.parent.name
            project_ds = project_ds[project_ds["covered_changes"].map(len) > 0].reset_index(drop=True)
            if len(project_ds) == 0:
                continue
            project_ds["covered_add_changes"] = project_ds.apply(lambda r: self.get_changed_lines(r, "ADD"), axis=1)
            project_ds["covered_del_changes"] = project_ds.apply(lambda r: self.get_changed_lines(r, "DELETE"), axis=1)
            project_ds = project_ds[project_ds["covered_add_changes"].map(len) > 0].reset_index(drop=True)
            ds_list.append(project_ds)

        ds = pd.concat(ds_list)

        SEP_TOKEN = "</s>"
        ds["input"] = ds.apply(
            lambda r: " ".join([r["before_repair_body"]] + [SEP_TOKEN] + r["covered_add_changes"]),
            axis=1,
        )
        ds["output"] = ds["after_repair_body"]
        validsize_ind = self.get_validsize_indices(ds)
        ds = ds.iloc[list(validsize_ind)].reset_index(drop=True)
        ds["ID"] = ds["project"]

        train_ds, valid_ds, test_ds = self.split_by_release(ds)

        return self.create_tensor_ds(train_ds), self.create_tensor_ds(valid_ds), self.create_tensor_ds(test_ds)