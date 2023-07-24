from sklearn.feature_extraction.text import TfidfVectorizer
from joblib import Parallel, delayed
from encoders.testRepair import TestRepairDataEncoder, Tokens
from encoders.preprocessing.commentRemoval import line_is_comment
from encoders.preprocessing.textDiff import get_hunk_diffs
from encoders.preprocessing.utils import get_hunk_lines
from diff_match_patch import diff_match_patch as dmp


class PrioritizedChangesDataEncoder(TestRepairDataEncoder):
    def remove_duplicate_documents(self, changes):
        unique_lines = set()
        unique_changes = []
        for change in changes:
            if change["doc"] not in unique_lines:
                unique_changes.append(change)
            unique_lines.add(change["doc"])
        return unique_changes

    def get_covered_change_documents(self, row):
        pass

    def get_sort_key(self, changed_doc):
        return (changed_doc["depth"], changed_doc["element"], -changed_doc["tfidf_sim"])

    def get_broken_code(self, row):
        broken_code = ""
        if "sourceChanges" in row["hunk"]:
            broken_code = " ".join([c["line"] for c in row["hunk"]["sourceChanges"]])
        return broken_code

    def prioritize_changed_documents(self, row):
        changes = self.get_covered_change_documents(row)
        changes = self.remove_duplicate_documents(changes)

        self.tokenizer.deprecation_warnings["sequence-length-is-longer-than-the-specified-maximum"] = True
        vectorizer = TfidfVectorizer(tokenizer=lambda d: self.tokenizer.tokenize(d))
        broken_code = self.get_broken_code(row)
        test_repr = broken_code if broken_code != "" else row["bSource"]["code"]
        vectors = vectorizer.fit_transform([test_repr] + [c["doc"] for c in changes])
        dense = vectors.todense()
        cosine_sim = (dense * dense[0].T).T.tolist()[0]
        for i, c in enumerate(changes):
            c["tfidf_sim"] = cosine_sim[i + 1]

        return sorted(changes, key=lambda c: self.get_sort_key(c))

    def preprocess(self, ds):
        ds = super().preprocess(ds)
        ds["prioritized_changes"] = Parallel(n_jobs=-1)(
            delayed(self.prioritize_changed_documents)(r) for _, r in ds.iterrows()
        )
        return ds

    def create_input(self, row, covered_changes):
        test_code = row["bSource"]["code"]
        breakge_start = min([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        breakge_end = max([l["lineNo"] for l in row["hunk"]["sourceChanges"]]) - row["bSource"]["startLine"]
        test_lines = test_code.split("\n")
        test_lines.insert(breakge_start, Tokens.BREAKAGE_START)
        test_lines.insert(breakge_end + 2, Tokens.BREAKAGE_END)
        test_lines = [l for l in test_lines if not line_is_comment(l)]
        test_context = " ".join(test_lines)

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
            self.tokenizer.deprecation_warnings["sequence-length-is-longer-than-the-specified-maximum"] = True
            pr_changes_cnt = len(r["prioritized_changes"])
            selected_changes = []
            for i in range(pr_changes_cnt):
                new_selected_changes = selected_changes + [r["prioritized_changes"][i]]
                new_inp = self.create_input(r, new_selected_changes)
                e_new_inp = self.tokenizer.encode(new_inp)
                if len(e_new_inp) <= self.args.max_seq:
                    selected_changes = new_selected_changes

            if len(selected_changes) == 0:
                selected_changes = [r["prioritized_changes"][0]]
            return (self.create_input(r, selected_changes), selected_changes)

        self.log("Prioritizing changed documents and creating inputs ...")
        ds_selected_changes = Parallel(n_jobs=-1)(delayed(select_changes)(r) for _, r in ds.iterrows())

        all_change_cnt = sum([len(r["prioritized_changes"]) for _, r in ds.iterrows()])
        included_change_cnt = sum([len(sc[1]) for sc in ds_selected_changes])
        included_change_p = round(100 * included_change_cnt / all_change_cnt, 1)
        self.log(f"In total, {included_change_p} % of covered changed documents are included in the input.")

        ds["input"] = [sc[0] for sc in ds_selected_changes]
        ds["output"] = ds.apply(lambda r: self.create_output(r), axis=1)
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

    def get_covered_change_documents(self, row):
        method_docs = self.create_documents(row["coveredMethodChanges"], 0)
        class_docs = self.create_documents(row["coveredClassChanges"], 1)
        return method_docs + class_docs


class FineGrainedHunksDataEncoder(HunksDataEncoder):
    def create_hunk_document(self, hunk):
        diffs = get_hunk_diffs(hunk)
        body = []
        annotated_body = []
        for type, text in diffs:
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


BEST_INPUT_MANIPULATOR = HunksDataEncoder
