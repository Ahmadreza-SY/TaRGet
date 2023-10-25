import json
from pathlib import Path


class CallGraphRepository:
    def __init__(self, args):
        self.call_graphs_cache = {}
        self.args = args

    def get_call_graph_depth(self, row, hunk, change):
        call_graph = self.get_call_graph(row["project"], row["bCommit"], row["name"])
        for node in call_graph["nodes"]:
            if hunk["scope"] == "method" and hunk["methodName"] == node["name"]:
                return node["depth"]
            elif hunk["scope"] == "class" and change["bPath"] == node["path"]:
                return node["depth"]

        return max([node["depth"] for node in call_graph["nodes"]])

    def get_call_graph(self, project, commit, test_name):
        key = f"{project}/{commit}/{test_name}"
        if key in self.call_graphs_cache:
            return self.call_graphs_cache[key]

        project_call_graphs_cache = self.get_project_call_graphs(project)
        self.call_graphs_cache.update(project_call_graphs_cache)

        if key not in self.call_graphs_cache:
            self.call_graphs_cache[key] = {}

        return self.call_graphs_cache[key]

    def get_project_call_graphs(self, project):
        ds_path = Path(self.args.dataset_dir)
        if project not in self.args.dataset_dir:
            ds_path = ds_path / project
        path = list(ds_path.rglob(f"call_graphs.json"))
        call_graphs = {}
        if len(path) == 1:
            call_graphs = json.loads(path[0].read_text())
        project_call_graphs = {}
        for commit, test_call_graphs in call_graphs.items():
            for test_name, call_graph in test_call_graphs.items():
                key = f"{project}/{commit}/{test_name}"
                project_call_graphs[key] = call_graph
        return project_call_graphs
