package edu.ahrsy.jparser.graph.dto;

import java.util.*;

public class CallGraphDTO {
  String root;
  List<CGNodeDTO> nodes;
  Map<String, HashSet<String>> graph;

  public CallGraphDTO(String root, List<CGNodeDTO> nodes, Map<String, HashSet<String>> graph) {
    this.root = root;
    this.nodes = nodes;
    this.graph = graph;
  }
}
