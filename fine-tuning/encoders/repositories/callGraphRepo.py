import json
from pathlib import Path
import logging


class CallGraphRepository:
    def __init__(self, args):
        self.call_graphs_cache = {}
        self.args = args
        self.logger = logging.getLogger("MAIN")

    def log(self, msg):
        self.logger.info(msg)

    def get_call_graph_depth(self, row, hunk, change):
        call_graph = self.get_call_graph(row["project"], row["bCommit"], row["name"])
        if len(call_graph) == 0:
            return 0
        node_depth = call_graph["node_depth"]
        max_node_depth = call_graph["max_node_depth"]
        if hunk["scope"] == "method":
            return node_depth.get(hunk["methodName"], max_node_depth)
        elif hunk["scope"] == "class":
            return node_depth.get(change["bPath"], max_node_depth)

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
                node_depth = {}
                max_node_depth = 0
                for node in call_graph["nodes"]:
                    if node["depth"] > max_node_depth:
                        max_node_depth = node["depth"]
                    if node["name"] not in node_depth:
                        node_depth[node["name"]] = node["depth"]
                    if node["path"] not in node_depth:
                        node_depth[node["path"]] = node["depth"]
                call_graph["node_depth"] = node_depth
                call_graph["max_node_depth"] = max_node_depth
                key = f"{project}/{commit}/{test_name}"
                project_call_graphs[key] = call_graph
        return project_call_graphs
