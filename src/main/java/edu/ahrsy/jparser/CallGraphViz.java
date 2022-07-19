package edu.ahrsy.jparser;

import guru.nidi.graphviz.attribute.Color;
import guru.nidi.graphviz.engine.Format;
import guru.nidi.graphviz.engine.Graphviz;
import guru.nidi.graphviz.model.MutableGraph;

import java.io.File;
import java.io.IOException;
import java.util.HashSet;
import java.util.Map;

import static guru.nidi.graphviz.model.Factory.mutGraph;
import static guru.nidi.graphviz.model.Factory.mutNode;

public class CallGraphViz {
  private static void visualizeGraph(Map<String, HashSet<String>> callGraph, String root) {
    MutableGraph graphV = mutGraph("example").setDirected(true);
    for (var entry : callGraph.entrySet()) {
      if (entry.getKey().equals(root))
        graphV.add(mutNode(entry.getKey()).add(Color.RED));
      for (var callee : entry.getValue())
        graphV.add(mutNode(entry.getKey()).addLink(mutNode(callee)));
    }
    try {
      Graphviz.fromGraph(graphV).render(Format.SVG).toFile(new File("example.svg"));
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }
}
