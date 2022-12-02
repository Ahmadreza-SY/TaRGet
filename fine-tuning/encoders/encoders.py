import logging
import numpy as np
from torch.utils.data import Dataset

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

    def log(self, msg):
        if self.args.rank == 0:
            self.logger.info(msg)

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

        self.log(f"The maximum length of inputs is {max(input_lengths)} and the mean is {round(np.mean(input_lengths))}")
        self.log(
            f"{round(100 * len(validsize_ind) / len(dataset), 1)} % ({len(validsize_ind)}/{len(dataset)}) samples had valid length (less that {self.args.max_seq})."
        )

        return validsize_ind

    def create_tensor_ds(self, dataset):
        inputs = self.tokenize(dataset, "pt")
        return TensorDataset(inputs["input_ids"], inputs["attention_mask"], inputs["labels"], dataset["ID"].values)

    def load_dataset(self):
        pass
