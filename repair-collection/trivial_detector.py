import json
from error_stats import ErrorStats


class TrivialDetector:
    def __init__(self, output_path):
        self.output_path = output_path
        self.elements = json.loads((output_path / "codeMining" / "test_elements.json").read_text())
        self.rename_refactorings = json.loads((output_path / "codeMining" / "rename_refactorings.json").read_text())

    def get_test_elements(self, test_name, commit):
        if commit not in self.elements or test_name not in self.elements[commit]:
            ErrorStats.update(ErrorStats.missing_te, commit)
            return set()
        test_elements = self.elements[commit][test_name]
        return set(test_elements["types"] + test_elements["executables"])

    def detect_trivial_repair(self, test_name, a_commit, b_commit):
        b_test_elements = self.get_test_elements(test_name, b_commit)
        a_test_elements = self.get_test_elements(test_name, a_commit)
        if a_commit not in self.rename_refactorings:
            ErrorStats.update(ErrorStats.missing_rr, a_commit)
        commit_refactorings = self.rename_refactorings.get(a_commit, {})
        trivial_types = []
        for ref in commit_refactorings:
            if ref["originalName"] in b_test_elements and ref["newName"] in a_test_elements:
                trivial_types.append(ref["refactoringType"])

        if trivial_types:
            return trivial_types
        else:
            return None
