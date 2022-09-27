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

    def tokenize(self, dataset, return_tensors):
        padding = False
        if return_tensors is not None:
            padding = "max_length"
        tokenizer = self.args.model_tokenizer_class.from_pretrained(self.args.model_name_or_path)
        model_inputs = tokenizer(
            dataset["input"].values.tolist(), return_tensors=return_tensors, padding=padding, max_length=self.args.max_seq
        )
        model_labels = tokenizer(
            text_target=dataset["after_repair"].values.tolist(),
            return_tensors=return_tensors,
            padding=padding,
            max_length=self.args.max_seq,
        )
        model_inputs["labels"] = model_labels["input_ids"]
        model_inputs["labels_attention_mask"] = model_labels["attention_mask"]
        return model_inputs

    def create_tensor_ds(self, dataset):
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
        inputs = self.tokenize(dataset.iloc[list(validsize_ind)].reset_index(drop=True), "pt")
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
        ds = pd.DataFrame({"input": buggy, "after_repair": fixed})
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