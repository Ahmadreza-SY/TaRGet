package edu.ahrsy.jparser.graph.dto;

import edu.ahrsy.jparser.graph.CGNode;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.spoon.Spoon;

import java.util.*;
import java.util.stream.Collectors;

public class Mapper {
  public static CallGraphDTO toDto(CallGraph callGraph, String srcPath) {
    var idGenerator = new IdGenerator();
    var nodes = new ArrayList<CGNodeDTO>();
    var graph = new HashMap<Integer, HashSet<Integer>>();

    // BFS graph traversal to keep ids in a specific order
    Queue<CGNode> queue = new LinkedList<>();
    Queue<Integer> depthQueue = new LinkedList<>();
    var visited = new HashSet<CGNode>();
    queue.add(callGraph.root);
    depthQueue.add(0);
    visited.add(callGraph.root);
    while (!queue.isEmpty()) {
      var node = queue.remove();
      var depth = depthQueue.remove();
      var nodeDto = new CGNodeDTO(idGenerator.getId(node.name),
              node.name,
              Spoon.getRelativePath(node.executable, srcPath),
              depth);
      nodes.add(nodeDto);
      for (var chNode : callGraph.graph.getOrDefault(node, new HashSet<>())) {
        if (!visited.contains(chNode)) {
          queue.add(chNode);
          depthQueue.add(depth + 1);
          visited.add(chNode);
        }
      }
    }

    for (var entry : callGraph.graph.entrySet())
      graph.put(idGenerator.getId(entry.getKey().name),
              entry.getValue()
                      .stream()
                      .map(n -> idGenerator.getId(n.name))
                      .collect(Collectors.toCollection(HashSet::new)));

    var rootDto = new CGNodeDTO(idGenerator.getId(callGraph.root.name),
            callGraph.root.name,
            Spoon.getRelativePath(callGraph.root.executable, srcPath),
            0);
    return new CallGraphDTO(rootDto, nodes, graph);
  }
}
