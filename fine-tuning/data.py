import logging
import pandas as pd
import numpy as np
from torch.utils.data import TensorDataset
from pathlib import Path
from utils import read_lines


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
        model_inputs["labels_attention_mask"] = model_labels["attention_mask"]
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
        return TensorDataset(
            inputs["input_ids"], inputs["attention_mask"], inputs["labels"], inputs["labels_attention_mask"]
        )

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

    def load_dataset(self):
        self.logger.info("Loading test repair datasets ...")

        ds_path = Path(self.args.dataset_dir)
        ds_list = []
        for project_ds_path in ds_path.glob("*/dataset.json"):
            project_ds = pd.read_json(project_ds_path)
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

        train_ds, valid_ds, test_ds = np.split(
            ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True),
            [int(0.8 * len(ds)), int(0.9 * len(ds))],
        )

        return self.create_tensor_ds(train_ds), self.create_tensor_ds(valid_ds), self.create_tensor_ds(test_ds)