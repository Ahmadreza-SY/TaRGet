import json


class TrivialDetector:
    def __init__(self, output_path):
        self.output_path = output_path
        self.elements = json.loads((output_path / "codeMining" / "test_elements.json").read_text())
        self.rename_refactorings = json.loads((output_path / "codeMining" / "rename_refactorings.json").read_text())

    def detect_trivial_repair(self, test_name, a_commit, b_commit):
        test_elements = self.elements[b_commit][test_name]
        test_elements = set(test_elements["types"] + test_elements["executables"])
        commit_refactorings = self.rename_refactorings[a_commit]
        for ref in commit_refactorings:
            if ref["originalName"] in test_elements:
                return ref["refactoringType"]
        return None
