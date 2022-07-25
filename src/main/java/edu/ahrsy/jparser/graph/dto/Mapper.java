package edu.ahrsy.jparser.graph.dto;

import edu.ahrsy.jparser.graph.CGNode;
import edu.ahrsy.jparser.graph.CallGraph;

import java.util.HashMap;
import java.util.HashSet;
import java.util.stream.Collectors;

public class Mapper {
  public static CallGraphDTO toDto(CallGraph callGraph, String srcPath) {
    var cgNodes = new HashSet<CGNode>();
    var graph = new HashMap<String, HashSet<String>>();
    for (var entry : callGraph.graph.entrySet()) {
      cgNodes.add(entry.getKey());
      cgNodes.addAll(entry.getValue());
      graph.put(entry.getKey().name,
              entry.getValue().stream().map(n -> n.name).collect(Collectors.toCollection(HashSet::new)));
    }

    return new CallGraphDTO(
            callGraph.root.name,
            cgNodes.stream().map(n -> new CGNodeDTO(n.name, n.getRelativePath(srcPath))).collect(Collectors.toList()),
            graph
    );
  }
}
