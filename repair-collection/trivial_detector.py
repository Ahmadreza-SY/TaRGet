import json


class TrivialDetector:
    TRIVIAL_REFACTORING_TYPES = [
        "RENAME_CLASS",
        "RENAME_METHOD",
        "MOVE_RENAME_CLASS",
    ]

    def __init__(self, output_path):
        self.output_path = output_path
        self.coverage = json.loads((output_path / "testExecution" / "coverage.json").read_text())
        self.refactorings = json.loads((output_path / "codeMining" / "refactorings.json").read_text())

    def detect_trivial_repair(self, test_name, a_commit, b_commit):
        test_coverage = self.coverage[b_commit][test_name]
        commit_refactorings = self.refactorings[a_commit]
        for ref in commit_refactorings:
            if ref["refactoringType"] not in TrivialDetector.TRIVIAL_REFACTORING_TYPES:
                continue
            src = ref["sourceFile"]
            if src in test_coverage:
                test_covered_lines = set(test_coverage[src])
                ref_lines = set(ref["bLines"])
                if len(test_covered_lines.intersection(ref_lines)) > 0:
                    return ref["refactoringType"]
        return None
