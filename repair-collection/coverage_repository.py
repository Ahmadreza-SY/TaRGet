import json
from common_utils import decompose_full_method_name
import copy


class ChangesRepository:
    def __init__(self, output_path):
        self.output_path = output_path
        self.changes = {}
        call_graphs_path = self.output_path / "codeMining" / "call_graphs.json"
        self.call_graphs = json.loads(call_graphs_path.read_text())

    def get_changes(self, commit):
        if commit in self.changes:
            return self.changes[commit]

        changes_path = self.get_changes_path()
        all_changes = json.loads(changes_path.read_text())
        if len(all_changes) == 0:
            print(f"No changes found for {commit}")
            return []
        for commit_changes in all_changes:
            self.changes[commit_changes["aCommit"]] = commit_changes["changes"]

        return self.changes[commit]

    def get_covered_changes(self, repair):
        changes = self.get_changes(repair["aCommit"])
        bCommit = repair["bCommit"]
        if bCommit not in self.call_graphs:
            print(f"No call graph found for {bCommit}")
            return []
        call_graph = self.call_graphs[repair["bCommit"]][repair["name"]]
        covered_elements = self.get_covered_elements(call_graph)
        covered_changes = []
        for change in changes:
            if change["name"] in covered_elements:
                _change = copy.deepcopy(change)
                _change["depth"] = covered_elements[change["name"]]
                covered_changes.append(_change)
        return covered_changes

    def get_changes_path(self):
        pass

    def get_covered_elements(self, call_graph):
        pass


class ClassChangesRepository(ChangesRepository):
    def get_changes_path(self):
        return self.output_path / "codeMining" / "sut_class_changes.json"

    def get_covered_elements(self, call_graph):
        covered_classes = {}
        for node in call_graph["nodes"]:
            if node["depth"] == 0:
                continue

            full_class_name, _, _ = decompose_full_method_name(node["name"])
            if full_class_name not in covered_classes or covered_classes[full_class_name] > node["depth"]:
                covered_classes[full_class_name] = node["depth"]

        return covered_classes


class MethodChangesRepository(ChangesRepository):
    def get_changes_path(self):
        return self.output_path / "codeMining" / "sut_method_changes.json"

    def get_covered_elements(self, call_graph):
        covered_methods = {}
        for node in call_graph["nodes"]:
            if node["depth"] == 0:
                continue
            covered_methods[node["name"]] = node["depth"]

        return covered_methods
