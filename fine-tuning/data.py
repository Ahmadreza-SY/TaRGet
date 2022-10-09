import logging
import pandas as pd
import numpy as np
from torch.utils.data import Dataset
from pathlib import Path
from utils import read_lines
from sklearn.feature_extraction.text import TfidfVectorizer


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

    def create_inputs_and_outputs(self, ds):
        pass

    def preprocess(self, ds):
        return ds[ds["covered_changes"].map(len) > 0].reset_index(drop=True)

    def load_dataset(self):
        self.logger.info("Loading test repair datasets ...")

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

        train_ds, valid_ds, test_ds = self.split_by_release(ds)
        ds_output_dir = self.args.output_dir / "splits"
        ds_output_dir.mkdir(exist_ok=True, parents=True)
        train_ds.to_json(ds_output_dir / "train.json", orient="records")
        valid_ds.to_json(ds_output_dir / "valid.json", orient="records")
        test_ds.to_json(ds_output_dir / "test.json", orient="records")

        return self.create_tensor_ds(train_ds), self.create_tensor_ds(valid_ds), self.create_tensor_ds(test_ds)


class TRBodyDataEncoder(TestRepairDataEncoder):
    def preprocess(self, ds):
        ds = super().preprocess(ds)
        ds["before_repair_body"] = ds["before_repair_body"].apply(
                lambda b: b[1:-1] if b.startswith("{") else b
        )
        ds["after_repair_body"] = ds["after_repair_body"].apply(
            lambda b: b[1:-1] if b.startswith("{") else b
        )
        ds = ds[ds['before_repair_body'] != ds['after_repair_body']].reset_index(drop=True)
        return ds


class PrioritizedChangesDataEncoder(TRBodyDataEncoder):
    def remove_duplicate_documents(self, changes):
        unique_lines = set()
        unique_changes = []
        for change in changes:
            if change["doc"] not in unique_lines:
                unique_changes.append(change)
            unique_lines.add(change["doc"])
        return unique_changes

    def get_change_documents(self, row):
        pass

    def get_sort_key(self, changed_doc):
        return (changed_doc["depth"], -changed_doc["tfidf_sim"])

    def prioritize_changed_documents(self, row):
        changes = self.get_change_documents(row)
        changes = self.remove_duplicate_documents(changes)

        vectorizer = TfidfVectorizer(tokenizer=lambda d: self.tokenizer.tokenize(d))
        vectors = vectorizer.fit_transform([row["before_repair"]] + [c["doc"] for c in changes])
        dense = vectors.todense()
        cosine_sim = (dense * dense[0].T).T.tolist()[0]
        for i, c in enumerate(changes):
            c["tfidf_sim"] = cosine_sim[i + 1]

        return sorted(changes, key=lambda c: self.get_sort_key(c))

    def preprocess(self, ds):
        ds = super().preprocess(ds)
        ds["prioritized_changes"] = ds.apply(lambda r: self.prioritize_changed_documents(r), axis=1)
        return ds

    def create_input(self, test_code, covered_changes):
        SEP_TOKEN = self.tokenizer.sep_token
        return " ".join([test_code] + [SEP_TOKEN] + covered_changes)
    
    def create_inputs_and_outputs(self, ds):
        self.logger.info("Prioritizing changed documents and creating inputs ...")
        included_change_p = []
        inputs = []
        for _, r in ds.iterrows():
            pr_changes = len(r["prioritized_changes"])
            selected_changes = []
            for i in range(pr_changes):
                new_selected_changes = selected_changes + [r["prioritized_changes"][i]["doc"]]
                new_inp = self.create_input(r["before_repair_body"], new_selected_changes)
                e_new_inp = self.tokenizer.encode(new_inp)
                if len(e_new_inp) <= self.args.max_seq:
                    selected_changes = new_selected_changes

            if len(selected_changes) == 0:
                selected_changes = [r["prioritized_changes"][0]["doc"]]
            inputs.append(self.create_input(r["before_repair_body"], selected_changes))
            included_change_p.append(len(selected_changes) / pr_changes)

        self.logger.info(
            f"On average, {round(100 * np.mean(included_change_p), 1)} % of covered changed documents are included in the input."
        )
        ds["input"] = inputs
        ds["output"] = ds["after_repair_body"]
        return ds


class TRTopLinesDataEncoder(PrioritizedChangesDataEncoder):
    def get_change_documents(self, row):
        changes = []
        for change in row["covered_changes"]:
            depth = change["depth"]
            for hunk in change["hunks"]:
                hunk_changes = []
                if "targetChanges" in hunk:
                    hunk_changes.extend(hunk["targetChanges"])
                if "sourceChanges" in hunk:
                    hunk_changes.extend(hunk["sourceChanges"])

                changes.extend(
                    [
                        {"doc": line_change["line"], "depth": depth, "change_type": line_change["type"]}
                        for line_change in hunk_changes
                    ]
                )

        return changes


class TRTopAddedLinesDataEncoder(PrioritizedChangesDataEncoder):
    def get_change_documents(self, row):
        added_changes = []
        deleted_changes = []
        for change in row["covered_changes"]:
            depth = change["depth"]
            for hunk in change["hunks"]:
                hunk_changes = []
                if "targetChanges" in hunk:
                    hunk_changes.extend(hunk["targetChanges"])
                if "sourceChanges" in hunk:
                    hunk_changes.extend(hunk["sourceChanges"])

                added_changes.extend(
                    [
                        {"doc": line_change["line"], "depth": depth, "change_type": line_change["type"]}
                        for line_change in hunk_changes
                        if line_change["type"] == "ADD"
                    ]
                )
                deleted_changes.extend(
                    [
                        {"doc": line_change["line"], "depth": depth, "change_type": line_change["type"]}
                        for line_change in hunk_changes
                        if line_change["type"] == "DELETE"
                    ]
                )

        if len(added_changes) > 0:
            return added_changes
        else:
            return deleted_changes


class TRTopHunksDataEncoder(PrioritizedChangesDataEncoder):
    def get_change_documents(self, row):
        changes = []
        for change in row["covered_changes"]:
            depth = change["depth"]
            for hunk in change["hunks"]:
                doc_lines = []
                if "targetChanges" in hunk:
                    doc_lines.extend([line_change["line"] for line_change in hunk["targetChanges"]])
                if "sourceChanges" in hunk:
                    doc_lines.extend([line_change["line"] for line_change in hunk["sourceChanges"]])

                changes.append({"doc": " ".join(doc_lines), "depth": depth, "change_type": hunk["type"]})

        return changes

class TRTopHunksSepDataEncoder(TRTopHunksDataEncoder):
    def create_input(self, test_code, covered_changes):
        SEP_TOKEN = self.tokenizer.sep_token
        return test_code + SEP_TOKEN + SEP_TOKEN.join(covered_changes)

class TRTopAddedHunksDataEncoder(PrioritizedChangesDataEncoder):
    def get_change_documents(self, row):
        added_changes = []
        deleted_changes = []
        for change in row["covered_changes"]:
            depth = change["depth"]
            for hunk in change["hunks"]:
                added_doc_lines = []
                deleted_doc_lines = []
                if "targetChanges" in hunk:
                    added_doc_lines.extend(
                        [line_change["line"] for line_change in hunk["targetChanges"] if line_change["type"] == "ADD"]
                    )
                    deleted_doc_lines.extend(
                        [line_change["line"] for line_change in hunk["targetChanges"] if line_change["type"] == "DELETE"]
                    )
                if "sourceChanges" in hunk:
                    added_doc_lines.extend(
                        [line_change["line"] for line_change in hunk["sourceChanges"] if line_change["type"] == "ADD"]
                    )
                    deleted_doc_lines.extend(
                        [line_change["line"] for line_change in hunk["sourceChanges"] if line_change["type"] == "DELETE"]
                    )

                if len(added_doc_lines) > 0:
                    added_changes.append({"doc": " ".join(added_doc_lines), "depth": depth, "change_type": hunk["type"]})
                if len(deleted_doc_lines) > 0:
                    deleted_changes.append({"doc": " ".join(deleted_doc_lines), "depth": depth, "change_type": hunk["type"]})

        if len(added_changes) > 0:
            return added_changes
        else:
            return deleted_changes

class TRTopAddedHunksSepDataEncoder(TRTopAddedHunksDataEncoder):
    def create_input(self, test_code, covered_changes):
        SEP_TOKEN = self.tokenizer.sep_token
        return test_code + SEP_TOKEN + SEP_TOKEN.join(covered_changes)