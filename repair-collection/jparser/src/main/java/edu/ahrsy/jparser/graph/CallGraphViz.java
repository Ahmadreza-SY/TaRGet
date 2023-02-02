package edu.ahrsy.jparser.graph;

import guru.nidi.graphviz.attribute.Color;
import guru.nidi.graphviz.engine.Format;
import guru.nidi.graphviz.engine.Graphviz;
import guru.nidi.graphviz.model.MutableGraph;

import java.io.File;
import java.io.IOException;

import static guru.nidi.graphviz.model.Factory.mutGraph;
import static guru.nidi.graphviz.model.Factory.mutNode;

public class CallGraphViz {
  public static void visualizeGraph(CallGraph callGraph) {
    MutableGraph graphV = mutGraph("example").setDirected(true);
    for (var entry : callGraph.graph.entrySet()) {
      if (entry.getKey().name.equals(callGraph.root.name))
        graphV.add(mutNode(entry.getKey().name).add(Color.RED));
      for (var callee : entry.getValue())
        graphV.add(mutNode(entry.getKey().name).addLink(mutNode(callee.name)));
    }
    try {
      Graphviz.fromGraph(graphV).render(Format.SVG).toFile(new File("example.svg"));
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }
}
