package edu.ahrsy.jparser.graph.dto;

import java.util.HashSet;
import java.util.List;
import java.util.Map;

public class CallGraphDTO {
  CGNodeDTO root;
  List<CGNodeDTO> nodes;
  Map<Integer, HashSet<Integer>> graph;

  public CallGraphDTO(CGNodeDTO root, List<CGNodeDTO> nodes, Map<Integer, HashSet<Integer>> graph) {
    this.root = root;
    this.nodes = nodes;
    this.graph = graph;
  }
}
