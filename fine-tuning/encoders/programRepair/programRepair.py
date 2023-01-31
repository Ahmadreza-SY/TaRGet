from ..encoders import BaseDataEncoder
import pandas as pd
from pathlib import Path
from tuning_utils import read_lines


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
        self.log("Loading train ...")
        train_dataset = self.read_split("train")
        self.log("Loading valid ...")
        valid_dataset = self.read_split("valid")
        self.log("Loading test ...")
        test_dataset = self.read_split("test")
        return train_dataset, valid_dataset, test_dataset
