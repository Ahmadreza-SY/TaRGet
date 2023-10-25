from encoders.abstractEncoder import AbstractDataEncoder, Tokens
from encoders.preprocessing.utils import get_hunk_lines


class BaseDataEncoder(AbstractDataEncoder):
    def create_hunk_document(self, hunk):
        src_lines, tgt_lines = get_hunk_lines(hunk)
        src_annotated_doc = ""
        if len(src_lines) > 0:
            src_annotated_doc = Tokens.DELETE + " ".join(src_lines) + Tokens.DELETE_END
        tgt_annotated_doc = ""
        if len(tgt_lines) > 0:
            tgt_annotated_doc = Tokens.ADD + " ".join(tgt_lines) + Tokens.ADD_END
        annotated_doc = Tokens.HUNK + src_annotated_doc + tgt_annotated_doc + Tokens.HUNK_END
        return annotated_doc

    def get_changed_documents(self, row):
        commit_changes = row["commitChanges"]
        change_docs = []
        for i, change in enumerate(commit_changes):
            for hunk in change["hunks"]:
                change_doc = self.create_changed_document(hunk)
                depth = self.call_graph_repo.get_call_graph_depth(row, hunk, change)
                scope = 0 if hunk["scope"] == "method" else 1
                change_doc.update({"depth": depth, "scope": scope})
                change_docs.append(change_doc)

        change_docs = self.remove_duplicate_change_documents(change_docs)

        tfidf_breakage = self.get_tfidf_sim(self.get_broken_code(row), change_docs)
        for i, changed_doc in enumerate(change_docs):
            changed_doc["tfidf_breakage"] = tfidf_breakage[i]
        return change_docs

    def get_sort_key(self, changed_doc):
        return (changed_doc["depth"], changed_doc["scope"], -round(changed_doc["tfidf_breakage"], 1))
