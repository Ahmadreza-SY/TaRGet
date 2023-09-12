from sklearn.feature_extraction.text import TfidfVectorizer
from encoders.testRepair import TestRepairDataEncoder, Tokens
from encoders.preprocessing.commentRemoval import line_is_comment, _remove_empty_hunks
from encoders.preprocessing.textDiff import get_hunk_diffs, _remove_whitespace_hunks
from encoders.preprocessing.codeFormatter import remove_repeating_whitespaces, format_sut_changes
from encoders.preprocessing.utils import get_hunk_lines
from encoders.preprocessing.processors import Processors
from diff_match_patch import diff_match_patch as dmp
from pathlib import Path
from encoders.preprocessing.editSequence import build_edit_sequence
import json
import copy
import swifter


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
        vectorizer = TfidfVectorizer(tokenizer=lambda t: t, lowercase=False)
        tokenized_docs = [self.tokenizer.encode(target)] + [c["annotated_doc_seq"] for c in changes]
        vectors = vectorizer.fit_transform(tokenized_docs)
        dense = vectors.todense()
        cosine_sim = (dense * dense[0].T).T.tolist()[0]
        return [cosine_sim[i + 1] for i in range(len(changes))]

    def prioritize_changed_documents(self, row):
        changes = self.get_changed_documents(row)
        changes = self.remove_duplicate_documents(changes)

        tfidf_breakage = self.get_tfidf_sim(self.get_broken_code(row), changes)
        tfidf_testsrc = self.get_tfidf_sim(row["bSource"]["code"], changes)
        for i, c in enumerate(changes):
            c["tfidf_breakage"] = round(tfidf_breakage[i], 1)
            c["tfidf_testsrc"] = round(tfidf_testsrc[i], 2)
        changes = [c for c in changes if c["tfidf_breakage"] > 0.0]
        return sorted(changes, key=lambda c: self.get_sort_key(c))

    def preprocess(self, ds):
        ds = super().preprocess(ds)
        self.log("Prioritizing changes")
        ds["prioritized_changes"] = ds.apply(lambda r: self.prioritize_changed_documents(r), axis=1)
        ds = ds.drop(columns=["allClassChanges", "coveredMethodChanges", "coveredClassChanges", "astActions"])
        ds = super().apply_processor(Processors.remove_empty_prioritized_changes, ds)
        return ds

    def create_test_context(self, row):
        test_code = row["bSource"]["code"]
        breakge_start = min([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        breakge_end = max([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        test_lines = test_code.split("\n")
        test_lines.insert(breakge_start, Tokens.BREAKAGE_START)
        test_lines.insert(breakge_end + 2, Tokens.BREAKAGE_END)
        test_lines = [l for l in test_lines if not line_is_comment(l)]
        test_context = " ".join(test_lines)
        test_context = remove_repeating_whitespaces(test_context)
        return test_context

    def create_input(self, test_context, covered_changes):
        return " ".join(
            [Tokens.TEST_CONTEXT, test_context] + [Tokens.REPAIR_CONTEXT] + [cc["annotated_doc"] for cc in covered_changes]
        )

    def create_output(self, row):
        repaired_code = ""
        if "targetChanges" in row["hunk"]:
            repaired_code = " ".join([c["line"] for c in row["hunk"]["targetChanges"]])

        return repaired_code

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
                if new_input_len <= self.args.max_seq:
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
        ds["output"] = ds.swifter.apply(lambda r: self.create_output(r), axis=1)

        ds["prioritized_changes"].apply(lambda p: [c.pop("annotated_doc_seq") for c in p])
        return ds


class HunksDataEncoder(PrioritizedChangesDataEncoder):
    def create_hunk_document(self, hunk):
        source_lines, target_lines = get_hunk_lines(hunk)
        doc = " ".join(source_lines + target_lines)

        if len(source_lines) > 0:
            source_lines.insert(0, Tokens.DELETE)
        if len(target_lines) > 0:
            target_lines.insert(0, Tokens.ADD)
        annotated_doc = " ".join([Tokens.HUNK] + source_lines + target_lines)

        return doc, annotated_doc

    def create_documents(self, covered_changes, element):
        change_docs = []
        for change in covered_changes:
            depth = change["depth"]
            for hunk in change["hunks"]:
                doc, annotated_doc = self.create_hunk_document(hunk)
                change_docs.append({"doc": doc, "annotated_doc": annotated_doc, "depth": depth, "element": element})
        return change_docs

    def get_changed_documents(self, row):
        method_docs = self.create_documents(row["coveredMethodChanges"], 0)
        class_docs = self.create_documents(row["coveredClassChanges"], 1)
        return method_docs + class_docs


class FineGrainedHunksDataEncoder(HunksDataEncoder):
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
        annotated_doc = " ".join([Tokens.HUNK] + annotated_body + [Tokens.HUNK_END])

        return doc, annotated_doc


class AllHunksDataEncoder(FineGrainedHunksDataEncoder):
    def preprocess_all_class_changes(self, changes):
        changes = format_sut_changes(changes)
        changes = _remove_whitespace_hunks(changes)
        changes = _remove_empty_hunks(changes)
        for change in changes:
            for hunk in change["hunks"]:
                doc, annotated_doc = self.create_hunk_document(hunk)
                hunk["doc"] = doc
                hunk["annotated_doc"] = annotated_doc
                hunk["annotated_doc_seq"] = self.tokenizer.encode(annotated_doc)
        return changes

    def get_all_class_changes(self, project, a_commit, changes_cache):
        key = f"{project}/{a_commit}"

        if key not in changes_cache:
            ds_path = Path(self.args.dataset_dir) / project
            changes_path = list(ds_path.rglob("sut_class_changes.json"))
            if len(changes_path) == 1:
                changes = json.loads(changes_path[0].read_text())
                for commit_changes in changes:
                    test_src_prefix = "src/test"
                    sut_commit_changes = [c for c in commit_changes["changes"] if test_src_prefix not in c["filePath"]]
                    sut_commit_changes = self.preprocess_all_class_changes(sut_commit_changes)
                    changes_cache[f"{project}/{commit_changes['aCommit']}"] = sut_commit_changes

        if key not in changes_cache:
            changes_cache[key] = []

        return copy.deepcopy(changes_cache.get(key, []))

    def read_data(self):
        ds = super().read_data()
        self.log(f"Reading and preprocessing all class changes")
        changes_cache = {}
        all_class_changes = []
        for _, row in ds.iterrows():
            changes = self.get_all_class_changes(row["project"], row["aCommit"], changes_cache)
            all_class_changes.append(changes)
        ds["allClassChanges"] = all_class_changes
        return ds

    def get_changed_documents(self, row):
        changes = row["allClassChanges"]
        change_docs = []
        change_repeat = {}
        for change in changes:
            for hunk in change["hunks"]:
                doc = hunk["doc"]
                change_docs.append(
                    {"doc": doc, "annotated_doc": hunk["annotated_doc"], "annotated_doc_seq": hunk["annotated_doc_seq"]}
                )
                if doc not in change_repeat:
                    change_repeat[doc] = 0
                change_repeat[doc] = change_repeat[doc] + 1
        for change_doc in change_docs:
            change_doc["repeat"] = change_repeat[change_doc["doc"]]
        return change_docs

    def get_sort_key(self, changed_doc):
        return (-changed_doc["tfidf_breakage"], -changed_doc["repeat"], -changed_doc["tfidf_testsrc"])


class AllHunksEditSequenceDataEncoder(AllHunksDataEncoder):
    def create_output(self, row):
        repaired_code = ""
        output, success = build_edit_sequence(row.bSource['code'], row.aSource['code'])
        if success:
            repaired_code = output

        return repaired_code

    def create_inputs_and_outputs(self, ds):
        ds = super(AllHunksEditSequenceDataEncoder, self).create_inputs_and_outputs(ds)
        num_without_output = len(ds[ds["output"].str.len() == 0].index)
        self.log(f'Removing {num_without_output} cases ({round(100 * num_without_output / len(ds.index), 2)} %) where output could not be generated')
        ds = ds[ds['output'].str.len() > 0]

        return ds


BEST_INPUT_MANIPULATOR = HunksDataEncoder
