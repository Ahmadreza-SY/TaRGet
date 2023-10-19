from sklearn.feature_extraction.text import TfidfVectorizer
from encoders.testRepair import TestRepairDataEncoder, Tokens
from encoders.preprocessing.commentRemoval import line_is_comment, remove_empty_hunks
from encoders.preprocessing.textDiff import get_hunk_diffs, remove_whitespace_hunks
from encoders.preprocessing.codeFormatter import format_sut_changes, add_padding_to_chars
from encoders.preprocessing.processors import Processors
from diff_match_patch import diff_match_patch as dmp
from pathlib import Path
from encoders.preprocessing.editSequence import build_edit_sequence, apply_edit_sequence, get_replace_pairs, REPLACE_OLDS, REPLACE_NEWS
from encoders.testRepair import Tokens
import json
import copy


class PrioritizedChangesDataEncoder(TestRepairDataEncoder):
    def remove_duplicate_documents(self, changes):
        unique_lines = set()
        unique_changes = []
        for change in changes:
            if change["doc"] not in unique_lines:
                unique_changes.append(change)
            unique_lines.add(change["doc"])
        return unique_changes

    def get_changed_documents(self, row):
        pass

    def get_sort_key(self, changed_doc):
        return (changed_doc["depth"], changed_doc["element"], -changed_doc["tfidf_breakage"])

    def get_broken_code(self, row):
        broken_code = ""
        if "sourceChanges" in row["hunk"]:
            broken_code = " ".join([c["line"] for c in row["hunk"]["sourceChanges"]])
        return broken_code

    def get_tfidf_sim(self, target, changes):
        vectorizer = TfidfVectorizer(tokenizer=lambda t: t, lowercase=False, token_pattern=None)
        tokenized_docs = [self.tokenizer.encode(target)] + [c["annotated_doc_seq"] for c in changes]
        vectors = vectorizer.fit_transform(tokenized_docs)
        dense = vectors.todense()
        cosine_sim = (dense * dense[0].T).T.tolist()[0]
        return [cosine_sim[i + 1] for i in range(len(changes))]

    def prioritize_changed_documents(self, row):
        changes = self.get_changed_documents(row)
        changes = self.remove_duplicate_documents(changes)

        tfidf_breakage = self.get_tfidf_sim(self.get_broken_code(row), changes)
        tfidf_testsrc = self.get_tfidf_sim(add_padding_to_chars(row["bSource"]["code"]), changes)
        for i, c in enumerate(changes):
            c["tfidf_breakage"] = round(tfidf_breakage[i], 1)
            c["tfidf_testsrc"] = round(tfidf_testsrc[i], 2)
        return sorted(changes, key=lambda c: self.get_sort_key(c))

    def preprocess(self, ds):
        ds = super().preprocess(ds)
        self.log("Prioritizing changes")
        ds["prioritized_changes"] = ds.apply(lambda r: self.prioritize_changed_documents(r), axis=1)
        ds = ds.drop(columns=["allClassChanges", "astActions"])
        ds = super().apply_processor(Processors.remove_empty_prioritized_changes, ds)
        return ds

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

    def create_input(self, test_context, covered_changes):
        return "".join(
            [Tokens.TEST_CONTEXT, test_context] + [Tokens.REPAIR_CONTEXT] + [cc["annotated_doc"] for cc in covered_changes]
        )

    def create_output(self, row):
        if "targetChanges" in row["hunk"] and len(row["hunk"]["targetChanges"]) > 0:
            repaired_code = " ".join([c["line"] for c in row["hunk"]["targetChanges"]])
        else:
            repaired_code = "// Deleted"
        return repaired_code

    @staticmethod
    def decode_outputs(row, outputs, tokenizer):
        preds = tokenizer.batch_decode(outputs, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        target = tokenizer.decode(
            tokenizer.encode(row["output"]), skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        return {"ID": row["ID"], "target": target, "preds": preds}

    def create_inputs_and_outputs(self, ds):
        def select_changes(r):
            pr_changes_cnt = len(r["prioritized_changes"])
            selected_changes = []
            test_context = self.create_test_context(r)
            test_context_e = self.tokenizer.encode(test_context)
            for i in range(pr_changes_cnt):
                new_selected_changes = selected_changes + [r["prioritized_changes"][i]]
                # The +2 is for Tokens.TEST_CONTEXT and Tokens.REPAIR_CONTEXT
                new_input_len = len(test_context_e) + sum(len(c["annotated_doc_seq"]) for c in new_selected_changes) + 2
                max_input_length = self.args.dataset_class.get_max_input_len(self.args.max_length)
                if new_input_len <= max_input_length:
                    selected_changes = new_selected_changes

            if len(selected_changes) == 0:
                selected_changes = [r["prioritized_changes"][0]]
            return (self.create_input(test_context, selected_changes), selected_changes)

        self.log("Creating inputs and outputs")
        ds_selected_changes = [select_changes(r) for _, r in list(ds.iterrows())]

        all_change_cnt = sum([len(r["prioritized_changes"]) for _, r in ds.iterrows()])
        included_change_cnt = sum([len(sc[1]) for sc in ds_selected_changes])
        included_change_p = round(100 * included_change_cnt / all_change_cnt, 1)
        self.log(f"In total, {included_change_p} % of covered changed documents are included in the input.")

        ds["input"] = [sc[0] for sc in ds_selected_changes]
        ds["output"] = ds.apply(lambda r: self.create_output(r), axis=1)

        ds["prioritized_changes"].apply(lambda p: [c.pop("annotated_doc_seq") for c in p])
        return ds


class AllHunksDataEncoder(PrioritizedChangesDataEncoder):
    def create_hunk_document(self, hunk):
        diffs = get_hunk_diffs(hunk)
        body = []
        annotated_body = []
        for type, text in diffs:
            text = text.strip()
            body.append(text)
            if type == dmp.DIFF_EQUAL:
                annotated_body.append(text)
            elif type == dmp.DIFF_DELETE:
                annotated_body.extend([Tokens.DELETE, text, Tokens.DELETE_END])
            elif type == dmp.DIFF_INSERT:
                annotated_body.extend([Tokens.ADD, text, Tokens.ADD_END])
        doc = " ".join(body)
        annotated_doc = "".join([Tokens.HUNK] + annotated_body + [Tokens.HUNK_END])

        return doc, annotated_doc

    def preprocess_all_class_changes(self, changes):
        changes = format_sut_changes(changes)
        changes = remove_whitespace_hunks(changes)
        changes = remove_empty_hunks(changes)
        for change in changes:
            for hunk in change["hunks"]:
                doc, annotated_doc = self.create_hunk_document(hunk)
                hunk["doc"] = doc
                hunk["annotated_doc"] = annotated_doc
                hunk["annotated_doc_seq"] = self.tokenizer.encode(annotated_doc)
        return changes

    def get_empty_changes_reason(self, changes, changes_wo_t, changes_pp):
        if len(changes) == 0:
            return "Originally Empty"
        elif len(changes_wo_t) == 0:
            return "All Test Source"
        elif len(changes_pp) == 0:
            if len(changes_wo_t) == len(changes):
                return "Preproccessing"
            else:
                return "Combination of Both"

    def log_empty_changes_stats(self, ds, stats):
        stats_cnt = {}
        for _, row in ds.iterrows():
            key = f"{row['project']}/{row['aCommit']}"
            if key in stats:
                reason = stats[key]
                stats_cnt.setdefault(reason, 0)
                stats_cnt[reason] += 1
        for k, v in stats_cnt.items():
            self.log(f"Got {v} empty changes due to {k}")

    def get_all_class_changes(self, project, a_commit, changes_cache, stats):
        key = f"{project}/{a_commit}"

        if key not in changes_cache:
            ds_path = Path(self.args.dataset_dir)
            if project not in self.args.dataset_dir:
                ds_path = ds_path / project
            changes_path = list(ds_path.rglob("sut_class_changes.json"))
            if len(changes_path) == 1:
                changes = json.loads(changes_path[0].read_text())
                for commit_changes in changes:
                    commit_changes_wo_t = [c for c in commit_changes["changes"] if not c["is_test_source"]]
                    commit_changes_pp = self.preprocess_all_class_changes(commit_changes_wo_t)
                    current_key = f"{project}/{commit_changes['aCommit']}"
                    changes_cache[current_key] = commit_changes_pp
                    if len(commit_changes_pp) == 0:
                        stats[current_key] = self.get_empty_changes_reason(
                            commit_changes["changes"], commit_changes_wo_t, commit_changes_pp
                        )

        if key not in changes_cache:
            stats[key] = "Not Found"
            changes_cache[key] = []

        return changes_cache.get(key, [])

    def read_data(self):
        ds = super().read_data()
        self.log(f"Reading and preprocessing all class changes")
        changes_cache = {}
        stats = {}
        all_class_changes = []
        for _, row in ds.iterrows():
            changes = self.get_all_class_changes(row["project"], row["aCommit"], changes_cache, stats)
            all_class_changes.append(changes)
        ds["allClassChanges"] = all_class_changes
        self.log_empty_changes_stats(ds, stats)
        return ds

    def create_changed_document(self, row, hunk):
        doc = hunk["doc"]
        return {"doc": doc, "annotated_doc": hunk["annotated_doc"], "annotated_doc_seq": hunk["annotated_doc_seq"]}

    def get_changed_documents(self, row):
        changes = row["allClassChanges"]
        change_docs = []
        change_repeat = {}
        for change in changes:
            for hunk in change["hunks"]:
                doc = hunk["doc"]
                change_docs.append(self.create_changed_document(row, hunk))
                if doc not in change_repeat:
                    change_repeat[doc] = 0
                change_repeat[doc] = change_repeat[doc] + 1
        for change_doc in change_docs:
            change_doc["repeat"] = change_repeat[change_doc["doc"]]
        return change_docs

    def get_sort_key(self, changed_doc):
        return (-changed_doc["tfidf_breakage"], -changed_doc["repeat"], -changed_doc["tfidf_testsrc"])


class EditSequenceDataEncoder(AllHunksDataEncoder):
    def create_output(self, row):
        repaired_code = ""
        output, success = build_edit_sequence(row.bSource["code"], row.aSource["code"])
        if success:
            repaired_code = output

        return repaired_code

    def create_inputs_and_outputs(self, ds):
        ds = super(EditSequenceDataEncoder, self).create_inputs_and_outputs(ds)
        num_without_output = len(ds[ds["output"].str.len() == 0].index)
        self.log(
            f"Removing {num_without_output} cases ({round(100 * num_without_output / len(ds.index), 2)} %) where edit sequence output could not be generated"
        )
        ds = ds[ds["output"].str.len() > 0].reset_index(drop=True)

        padded_targets = ds["aSource"].apply(lambda r: add_padding_to_chars(r["code"]))
        applied_seqs = ds.apply(lambda r: apply_edit_sequence(r["bSource"]["code"], r["output"]), axis=1)
        applied_seqs = applied_seqs.apply(lambda r: add_padding_to_chars(r) if r else None)
        applied_successes = padded_targets == applied_seqs
        applied_failure_count = len(applied_successes) - applied_successes.sum()
        self.log(f"{applied_failure_count} cases ({round(100 * applied_failure_count / len(applied_successes), 2)} %) where the edit sequence was not successfully applied")

        return ds

    @staticmethod
    def remove_special_tokens(edit_seq, tokenizer):
        new_edit_seq = ""
        tokens = []
        for _, v in tokenizer.special_tokens_map:
            if type(v) == list:
                tokens.extend([t for t in v if t not in REPLACE_NEWS and t not in REPLACE_OLDS and t != Tokens.BREAKAGE_END])
            else:
                if v not in REPLACE_NEWS and v not in REPLACE_OLDS and v != Tokens.BREAKAGE_END:
                    tokens.append(v)

        while len(edit_seq) > 0:
            checked = False
            while not checked:
                checked = True
                for t in tokens:
                    if edit_seq.startswith(t):
                        edit_seq = edit_seq[len(t):]
                        if (len(new_edit_seq) == 0 or new_edit_seq.endswith(" ")) and edit_seq.startswith(" "):
                            edit_seq = edit_seq[1:]
                        checked = False

            new_edit_seq += edit_seq[0]
            edit_seq = edit_seq[1:]

        return new_edit_seq

    @staticmethod
    def decode_outputs(row, outputs, tokenizer):
        pred_edit_seqs = tokenizer.batch_decode(outputs, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        target_edit_seq = row["output"]

        target_edit_seq = EditSequenceDataEncoder.remove_special_tokens(target_edit_seq, tokenizer)

        for i in range(len(pred_edit_seqs)):
            pred_edit_seqs[i] = EditSequenceDataEncoder.remove_special_tokens(pred_edit_seqs[i], tokenizer)

        pred_edit_pairs = [get_replace_pairs(es) for es in pred_edit_seqs]
        target_edit_pairs = get_replace_pairs(target_edit_seq)

        preds, targets = [], []

        src, target = row["bSource"]["code"], add_padding_to_chars(row["aSource"]["code"])

        for i in range(len(pred_edit_pairs)):
            curr_pred_pairs = pred_edit_pairs[i]

            applied_pred = apply_edit_sequence(src, pred_edit_seqs[i], curr_pred_pairs)

            if not applied_pred:
                preds.append("Invalid")
            else:
                start = min([applied_pred.index(n) for _, n in curr_pred_pairs])
                end = max([applied_pred.index(n) + len(n) for _, n in curr_pred_pairs])

                start = [0].extend([i + 1 for i, char in enumerate(applied_pred) if i < start and char == ";"])[-1]
                end = [-1].extend([i + 1 for i, char in reversed(list(enumerate(applied_pred))) if i > end and char == ";"])[
                    -1
                ]

                preds.append(applied_pred[start:end])

        if not target_edit_pairs:
            target = "Invalid"
        else:
            try:
                edit_start = min([target.index(n) for _, n in target_edit_pairs])
                edit_end = max([target.index(n) + len(n) for _, n in target_edit_pairs])
            except Exception:
                target = apply_edit_sequence(src, target_edit_seq, target_edit_pairs)
                edit_start = min([target.index(n) for _, n in target_edit_pairs])
                edit_end = max([target.index(n) + len(n) for _, n in target_edit_pairs])

            start = [0]
            start.extend([i + 1 for i, char in enumerate(target) if i < edit_start and char == ";"])
            start = start[-1]
            end = [-1]
            end.extend([i + 1 for i, char in reversed(list(enumerate(target))) if i > edit_end and char == ";"])
            end = end[-1]

            target = target[start : end + 1]

        return {"ID": row["ID"], "target": target, "preds": preds, "target_es": target_edit_seq, "pred_es": pred_edit_seqs}


class ASTElementsDataEncoder(AllHunksDataEncoder):
    def create_changed_document(self, row, hunk):
        changed_doc = super().create_changed_document(row, hunk)
        changed_doc["equal_ast_elements"] = 0
        changed_doc["similar_ast_elements"] = 0
        if "sourceElements" not in row["hunk"]:
            return changed_doc
        for t_e in row["hunk"]["sourceElements"]:
            for sut_e in hunk["sourceElements"]:
                if t_e["value"] == sut_e["value"]:
                    if t_e["type"] == sut_e["type"]:
                        changed_doc["equal_ast_elements"] += 1
                    else:
                        changed_doc["similar_ast_elements"] += 1
        return changed_doc

    def get_sort_key(self, changed_doc):
        return (
            -changed_doc["equal_ast_elements"],
            -changed_doc["similar_ast_elements"],
            -changed_doc["tfidf_breakage"],
            -changed_doc["repeat"],
            -changed_doc["tfidf_testsrc"],
        )
