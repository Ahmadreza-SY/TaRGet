from encoders.baseEncoder import BaseDataEncoder
from encoders.preprocessing.codeFormatter import add_padding_to_chars


class SimOrderDataEncoder(BaseDataEncoder):
    def get_changed_documents(self, row):
        commit_changes = row["commitChanges"]
        change_docs = []
        change_repeat = {}
        for i, change in enumerate(commit_changes):
            for hunk in change["hunks"]:
                change_doc = self.create_changed_document(hunk)
                annotated_doc = change_doc["annotated_doc"]
                change_docs.append(change_doc)
                if annotated_doc not in change_repeat:
                    change_repeat[annotated_doc] = 0
                change_repeat[annotated_doc] += 1

        for change_doc in change_docs:
            change_doc["repeat"] = change_repeat[change_doc["annotated_doc"]]

        change_docs = self.remove_duplicate_change_documents(change_docs)

        tfidf_breakage = self.get_tfidf_sim(self.get_broken_code(row), change_docs)
        tfidf_testsrc = self.get_tfidf_sim(add_padding_to_chars(row["bSource"]["code"]), change_docs)
        for i, changed_doc in enumerate(change_docs):
            changed_doc["tfidf_breakage"] = tfidf_breakage[i]
            changed_doc["tfidf_testsrc"] = tfidf_testsrc[i]

        return change_docs

    def get_sort_key(self, changed_doc):
        return (-round(changed_doc["tfidf_breakage"], 1), -changed_doc["repeat"], -round(changed_doc["tfidf_testsrc"], 2))



