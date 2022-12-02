import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from .testRepair import BodyDataEncoder


class PrioritizedChangesDataEncoder(BodyDataEncoder):
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

    def create_output(self, row):
        SEP_TOKEN = self.tokenizer.sep_token
        if self.args.ground_truth == "repaired_body":
            return row["after_repair_body"]
        elif self.args.ground_truth == "repair_changes_hsep":
            return SEP_TOKEN.join(
                [
                    " ".join(
                        [c["line"] for c in h.get("sourceChanges", [])] + [c["line"] for c in h.get("targetChanges", [])]
                    )
                    for h in row["repair_changes"]
                ]
            )
        elif self.args.ground_truth == "repair_changes_stsep":
            hunk_changes = []
            for h in row["repair_changes"]:
                src_changes = [c["line"] for c in h.get("sourceChanges", [])]
                tr_changes = [c["line"] for c in h.get("targetChanges", [])]
                line_changes = []
                if len(src_changes) > 0:
                    line_changes.append(" ".join(src_changes))
                if len(tr_changes) > 0:
                    line_changes.append(" ".join(tr_changes))
                hunk_changes.append(SEP_TOKEN.join(line_changes))

            return SEP_TOKEN.join(hunk_changes)
        elif self.args.ground_truth == "repair_changes_tok":
            hunk_changes = []
            for h in row["repair_changes"]:
                src_changes = [c["line"] for c in h.get("sourceChanges", [])]
                tr_changes = [c["line"] for c in h.get("targetChanges", [])]
                line_changes = []
                if len(src_changes) > 0:
                    line_changes.append("DEL " + " ".join(src_changes))
                if len(tr_changes) > 0:
                    line_changes.append("ADD " + " ".join(tr_changes))
                hunk_changes.append(" ".join(line_changes))

            return " ".join(hunk_changes)

    def create_inputs_and_outputs(self, ds):
        self.log("Prioritizing changed documents and creating inputs ...")
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

        self.log(
            f"On average, {round(100 * np.mean(included_change_p), 1)} % of covered changed documents are included in the input."
        )
        ds["input"] = inputs
        ds["output"] = ds.apply(lambda r: self.create_output(r), axis=1)
        return ds


class TopLinesDataEncoder(PrioritizedChangesDataEncoder):
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


class TopAddedLinesDataEncoder(PrioritizedChangesDataEncoder):
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


class TopHunksDataEncoder(PrioritizedChangesDataEncoder):
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


class TopHunksSepDataEncoder(TopHunksDataEncoder):
    def create_input(self, test_code, covered_changes):
        SEP_TOKEN = self.tokenizer.sep_token
        return test_code + SEP_TOKEN + SEP_TOKEN.join(covered_changes)


class TopAddedHunksDataEncoder(PrioritizedChangesDataEncoder):
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


class TopAddedHunksSepDataEncoder(TopAddedHunksDataEncoder):
    def create_input(self, test_code, covered_changes):
        SEP_TOKEN = self.tokenizer.sep_token
        return test_code + SEP_TOKEN + SEP_TOKEN.join(covered_changes)


BEST_INPUT_MANIPULATOR = TopHunksDataEncoder
