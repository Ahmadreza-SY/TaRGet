from encoders.testRepair.inputManipulators import BEST_INPUT_MANIPULATOR


class FirstDepthCoverageDataEncoder(BEST_INPUT_MANIPULATOR):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        before_len = len(ds)
        ds["prioritized_changes"] = ds["prioritized_changes"].apply(lambda p: [c for c in p if c["depth"] == 1])
        ds = ds[ds["prioritized_changes"].map(len) > 0].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to no first-depth covered changes.")
        return ds
