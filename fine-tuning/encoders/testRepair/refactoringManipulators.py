from encoders.testRepair.inputManipulators import BEST_INPUT_MANIPULATOR


class TestRefactorEXDataEncoder(BEST_INPUT_MANIPULATOR):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        before_len = len(ds)
        ds = ds[~ds["refactor"]].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to refactor in test code.")
        return ds


class CovRefactorINDataEncoder(BEST_INPUT_MANIPULATOR):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        before_len = len(ds)
        ds["refactor_cov"] = ds["covered_changes"].apply(lambda cov: any(c["refactor"] for c in cov))
        ds = ds[ds["refactor_cov"]].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to no refactor in covered code.")
        return ds


class CovINTestEXRefactorDataEncoder(BEST_INPUT_MANIPULATOR):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        before_len = len(ds)
        ds["refactor_cov"] = ds["covered_changes"].apply(lambda cov: any(c["refactor"] for c in cov))
        ds = ds[(ds["refactor_cov"]) & (~ds["refactor"])].reset_index(drop=True)
        self.log(f"Removed {before_len - len(ds)} rows due to no refactor in covered code and refactor in test code.")
        return ds
