from encoders.testRepair.inputManipulators import BEST_INPUT_MANIPULATOR


class TrivialRmDataEncoder(BEST_INPUT_MANIPULATOR):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        before_len = len(ds)
        ds = ds[ds["trivial"].isna()].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} trivial test repairs")
        return ds

