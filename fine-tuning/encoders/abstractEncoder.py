import pandas as pd
import numpy as np
from pathlib import Path
import inspect
from encoders.preprocessing.processors import Processors
import sys
import logging
import pickle
from encoders.preprocessing.commentRemoval import line_is_comment
from encoders.preprocessing.codeFormatter import add_padding_to_chars
from encoders.preprocessing.processors import Processors
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from encoders.repositories.changeRepo import ChangeRepository
from encoders.repositories.callGraphRepo import CallGraphRepository


class Tokens:
    BREAKAGE_START = "[<BREAKAGE>]"
    BREAKAGE_END = "[</BREAKAGE>]"
    TEST_CONTEXT = "[<TESTCONTEXT>]"
    REPAIR_CONTEXT = "[<REPAIRCONTEXT>]"
    DELETE = "[<DEL>]"
    ADD = "[<ADD>]"
    HUNK = "[<HUNK>]"
    HUNK_END = "[</HUNK>]"


class AbstractDataEncoder:
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger("MAIN")
        self.change_repo = ChangeRepository(args)
        self.call_graph_repo = CallGraphRepository(args)

    def create_hunk_document(self, hunk):
        pass

    def get_changed_documents(self, row):
        pass

    def get_sort_key(self, changed_doc):
        pass

    def log(self, msg):
        self.logger.info(msg)

    def get_special_tokens_class(self):
        return Tokens

    def create_tokenizer(self):
        self.tokenizer = self.args.model_tokenizer_class.from_pretrained(self.args.model_path)
        new_special_tokens = {
            "additional_special_tokens": self.tokenizer.additional_special_tokens
            + [v for k, v in inspect.getmembers(self.get_special_tokens_class()) if not k.startswith("_")]
        }
        self.tokenizer.add_special_tokens(new_special_tokens)
        self.tokenizer.deprecation_warnings["sequence-length-is-longer-than-the-specified-maximum"] = True
        self.tokenizer.save_pretrained(str(self.args.output_dir / "tokenizer"))

    def shuffle(self, ds):
        return ds.sample(frac=1.0, random_state=self.args.random_seed).reset_index(drop=True)

    def split_by_commit(self, ds):
        projects = ds["project"].unique().tolist()
        train_ds_list, valid_ds_list, test_ds_list = [], [], []
        for project in projects:
            project_ds = ds[ds["project"] == project].sort_values("aCommitTime").reset_index(drop=True)

            dup_ind = project_ds[~project_ds["aCommit"].duplicated()].index.tolist()[1:]
            train_size = int(self.args.train_size * len(project_ds))
            train_dup_ind = [i for i in dup_ind if i <= (train_size - 1)]
            if len(train_dup_ind) == 0:
                train_split_i = dup_ind[0]
            else:
                train_split_i = train_dup_ind[-1]
            p_train_ds, p_eval_ds = np.split(project_ds, [train_split_i])

            # stratified test and valid split
            p_eval_list = [np.split(g, [int(0.25 * len(g))]) for _, g in p_eval_ds.groupby("aCommit")]
            p_valid_ds = pd.concat([t[0] for t in p_eval_list])
            p_test_ds = pd.concat([t[1] for t in p_eval_list])

            train_ds_list.append(p_train_ds)
            valid_ds_list.append(p_valid_ds)
            test_ds_list.append(p_test_ds)

        train_ds = pd.concat(train_ds_list)
        valid_ds = pd.concat(valid_ds_list)
        test_ds = pd.concat(test_ds_list)

        # Shuffle splits
        train_ds = self.shuffle(train_ds)
        valid_ds = self.shuffle(valid_ds)
        test_ds = self.shuffle(test_ds)

        return train_ds, valid_ds, test_ds

    def get_broken_code(self, row):
        broken_code = ""
        if "sourceChanges" in row["hunk"]:
            broken_code = " ".join([c["line"] for c in row["hunk"]["sourceChanges"]])
        return broken_code

    def get_repaired_code(self, row):
        repaired_code = ""
        if "targetChanges" in row["hunk"] and len(row["hunk"]["targetChanges"]) > 0:
            repaired_code = " ".join([c["line"] for c in row["hunk"]["targetChanges"]])
        return repaired_code

    def get_tfidf_sim(self, target, changes):
        vectorizer = TfidfVectorizer(tokenizer=lambda t: t, lowercase=False, token_pattern=None)
        tokenized_docs = [self.tokenizer.encode(target)] + [c["annotated_doc_seq"] for c in changes]
        vectors = vectorizer.fit_transform(tokenized_docs)
        dense = vectors.todense()
        cosine_sim = (dense * dense[0].T).T.tolist()[0]
        return [cosine_sim[i + 1] for i in range(len(changes))]

    def create_test_context(self, row):
        test_code = row["bSource"]["code"]
        break_s = min([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        break_e = max([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        test_lines = test_code.split("\n")
        test_lines = [add_padding_to_chars(l) for l in test_lines]
        test_lines[break_s] = Tokens.BREAKAGE_START + test_lines[break_s]
        test_lines[break_e] = test_lines[break_e] + Tokens.BREAKAGE_END
        test_lines = [l for l in test_lines if not line_is_comment(l) and len(l) > 0 and not l.isspace()]
        test_context = (
            " ".join(test_lines)
            .replace(f" {Tokens.BREAKAGE_START}", Tokens.BREAKAGE_START)
            .replace(f"{Tokens.BREAKAGE_END} ", Tokens.BREAKAGE_END)
        )
        return test_context

    def create_changed_document(self, hunk):
        if "annotated_doc" not in hunk:
            hunk["annotated_doc"] = self.create_hunk_document(hunk)
        if "annotated_doc_seq" not in hunk:
            hunk["annotated_doc_seq"] = self.tokenizer.encode(hunk["annotated_doc"])
        change_doc = {"annotated_doc": hunk["annotated_doc"], "annotated_doc_seq": hunk["annotated_doc_seq"]}
        return change_doc

    def create_input(self, test_context, changed_docs):
        return "".join(
            [Tokens.TEST_CONTEXT, test_context] + [Tokens.REPAIR_CONTEXT] + [cc["annotated_doc"] for cc in changed_docs]
        )

    def create_output(self, row):
        repaired_code = self.get_repaired_code(row)
        if not repaired_code:
            repaired_code = "// Deleted"
        return repaired_code

    @staticmethod
    def decode_outputs(row, outputs, tokenizer):
        preds = tokenizer.batch_decode(outputs, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        target = row["output"]
        return {"ID": row["ID"], "target": target, "preds": preds}

    def save_oversized_ids(self, ds):
        oversized_ids = []
        for _, row in ds.iterrows():
            if all(c["selected"] is False for c in row["prioritized_changes"]):
                oversized_ids.append(row["ID"])
        if len(oversized_ids) > 0:
            splits_dir = self.args.output_dir / "splits"
            splits_dir.mkdir(exist_ok=True, parents=True)
            pd.DataFrame({"id": oversized_ids}).to_csv(splits_dir / f"all_os_ids.csv", index=False)

    def select_changes(self, row):
        pr_changes_cnt = len(row["prioritized_changes"])
        selected_changes = []
        test_context = self.create_test_context(row)
        test_context_e = self.tokenizer.encode(test_context)
        for i in range(pr_changes_cnt):
            row["prioritized_changes"][i]["selected"] = False
            new_selected_changes = selected_changes + [row["prioritized_changes"][i]]
            # The +2 is for Tokens.TEST_CONTEXT and Tokens.REPAIR_CONTEXT
            new_input_len = len(test_context_e) + sum(len(c["annotated_doc_seq"]) for c in new_selected_changes) + 2
            max_input_length = self.args.dataset_class.get_max_input_len(self.args.max_length)
            if new_input_len <= max_input_length:
                selected_changes = new_selected_changes
                row["prioritized_changes"][i]["selected"] = True

        if len(selected_changes) == 0:
            selected_changes = [row["prioritized_changes"][0]]
        return (self.create_input(test_context, selected_changes), selected_changes)

    def create_inputs_and_outputs(self, ds):
        self.log("Creating inputs and outputs")
        ds_selected_changes = [self.select_changes(r) for _, r in list(ds.iterrows())]

        all_change_cnt = sum([len(r["prioritized_changes"]) for _, r in ds.iterrows()])
        included_change_cnt = sum([len(sc[1]) for sc in ds_selected_changes])
        included_change_p = round(100 * included_change_cnt / all_change_cnt, 1)
        self.log(f"In total, {included_change_p} % of covered changed documents are included in the input.")

        ds["input"] = [sc[0] for sc in ds_selected_changes]
        ds["output"] = ds.apply(lambda r: self.create_output(r), axis=1)

        ds["prioritized_changes"].apply(lambda p: [c.pop("annotated_doc_seq") for c in p])

        ds["input"] = ds["input"].str.strip()
        ds["output"] = ds["output"].str.strip()
        self.save_oversized_ids(ds)
        return ds

    def apply_processor(self, processor, ds):
        before_len = len(ds)
        self.log(f"Applying processor {processor.__name__}")
        ds = processor(ds, self.args)
        if before_len != len(ds):
            self.log(f"Removed {before_len - len(ds)} rows by the {processor.__name__} processor")
        return ds

    def prioritize_changed_documents(self, row):
        changed_docs = self.get_changed_documents(row)
        return sorted(changed_docs, key=lambda c: self.get_sort_key(c))

    def preprocess(self, ds):
        processors = [
            Processors.remove_empty_changes,
            Processors.remove_comment_repairs,
            Processors.remove_no_source_changes,
            Processors.remove_out_of_range,
            Processors.remove_oversized_inputs,
            Processors.format_code,
        ]
        for processor in processors:
            ds = self.apply_processor(processor, ds)

        self.log("Prioritizing changes")
        ds["prioritized_changes"] = ds.apply(lambda r: self.prioritize_changed_documents(r), axis=1)
        ds = self.apply_processor(Processors.remove_empty_prioritized_changes, ds)
        ds = ds.drop(columns=["commitChanges"])
        return ds

    def remove_duplicate_change_documents(self, change_docs):
        unique_docs = set()
        unique_change_docs = []
        for change_doc in change_docs:
            if change_doc["annotated_doc"] not in unique_docs:
                unique_change_docs.append(change_doc)
            unique_docs.add(change_doc["annotated_doc"])
        return unique_change_docs

    def merge_train_with_trivial(self, train_ds, trivial_ds):
        projects = trivial_ds["project"].unique().tolist()
        train_trivial_ds_list = []
        for project in projects:
            latest_train_time = train_ds[train_ds["project"] == project]["aCommitTime"].max()
            project_trivial_ds = trivial_ds[trivial_ds["project"] == project].reset_index(drop=True)
            project_train_trivial_ds = project_trivial_ds[
                project_trivial_ds["aCommitTime"] <= latest_train_time
            ].reset_index(drop=True)
            if len(project_train_trivial_ds) > 0:
                train_trivial_ds_list.append(project_train_trivial_ds)

        train_trivial_ds = None
        if len(train_trivial_ds_list) > 0:
            train_trivial_ds = pd.concat(train_trivial_ds_list)

        if train_trivial_ds is None or len(train_trivial_ds) == 0:
            self.log("No trivial repairs to add to train")
        else:
            train_ds = pd.concat([train_ds, train_trivial_ds])
            train_ds = self.shuffle(train_ds)
            self.log(f"Added {len(train_trivial_ds)} trivial test repairs to the train set")

        return train_ds

    def read_data(self):
        ds_path = Path(self.args.dataset_dir)
        ds_list = []
        ds_paths = list(ds_path.rglob("dataset.json"))
        for project_ds_path in ds_paths:
            project_ds = pd.read_json(project_ds_path)
            project_ds = project_ds.drop(columns=["astActions"])
            project_ds["project"] = f"{project_ds_path.parent.parent.name}/{project_ds_path.parent.name}"
            if len(project_ds) == 0:
                continue
            ds_list.append(project_ds)

        if len(ds_list) == 0:
            raise Exception(f"No datasets found in {ds_path}")
        ds = pd.concat(ds_list)
        ds["commitChanges"] = ds.apply(
            lambda row: self.change_repo.get_commit_changes(row["project"], row["aCommit"]), axis=1
        )
        self.change_repo.log_stats(ds)
        return ds

    def create_datasets(self):
        self.log("Creating test repair datasets...")
        self.create_tokenizer()

        ds_output_dir = self.args.output_dir / "splits"
        train_file = ds_output_dir / "train.pkl"
        valid_file = ds_output_dir / "valid.pkl"
        test_file = ds_output_dir / "test.pkl"

        if train_file.exists() and valid_file.exists() and test_file.exists():
            self.log("Loading train, valid, and test datasets from disk...")
            train_ds = pickle.load(open(str(train_file), "rb"))
            valid_ds = pickle.load(open(str(valid_file), "rb"))
            test_ds = pickle.load(open(str(test_file), "rb"))
        else:
            original_ds = self.read_data()
            self.log(f"Read {len(original_ds)} samples from {original_ds['project'].nunique()} projects")

            ds = self.preprocess(original_ds)
            self.log(f"Got {len(ds)} samples after preprocessing")
            if len(ds) == 0:
                self.log(f"Aborting ...")
                sys.exit()

            ds = self.create_inputs_and_outputs(ds)

            trivial_ds = ds[~ds["trivial"].isna()].reset_index(drop=True)
            ds = self.apply_processor(Processors.remove_trivial_repairs, ds)

            train_ds, valid_ds, test_ds = self.split_by_commit(ds)

            train_ds = self.merge_train_with_trivial(train_ds, trivial_ds)

            self.log("Creating datasets")
            og_ds_s = len(train_ds) + len(valid_ds) + len(test_ds)
            train_ds = self.args.dataset_class(train_ds, self.tokenizer, "train", self.args)
            valid_ds = self.args.dataset_class(valid_ds, self.tokenizer, "valid", self.args)
            test_ds = self.args.dataset_class(test_ds, self.tokenizer, "test", self.args)
            new_ds_s = len(train_ds) + len(valid_ds) + len(test_ds)
            valid_per = round(100 * new_ds_s / og_ds_s, 1)
            self.log(
                f"{valid_per} % ({new_ds_s}/{og_ds_s}) samples had less than max_length ({self.args.max_length}) tokens."
            )
            self.log("Pickling datasets")
            pickle.dump(train_ds, open(str(train_file), "wb"))
            pickle.dump(valid_ds, open(str(valid_file), "wb"))
            pickle.dump(test_ds, open(str(test_file), "wb"))

        ds_len = len(train_ds) + len(valid_ds) + len(test_ds)
        self.log(f"Train: {len(train_ds)} ({round(100 * len(train_ds) / ds_len, 1)} %)")
        self.log(f"Valid: {len(valid_ds)} ({round(100 * len(valid_ds) / ds_len, 1)} %)")
        self.log(f"Test: {len(test_ds)} ({round(100 * len(test_ds) / ds_len, 1)} %)")
