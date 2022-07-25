package edu.ahrsy.jparser.graph;

import com.google.gson.Gson;
import edu.ahrsy.jparser.graph.dto.Mapper;
import edu.ahrsy.jparser.utils.FileUtils;
import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.declaration.CtExecutable;

import java.nio.file.Path;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class CallGraph {
  public Map<CGNode, HashSet<CGNode>> graph;
  public CGNode root;

  public CallGraph(CtExecutable<?> root) {
    this.graph = new HashMap<>();
    this.root = new CGNode(root);
  }

  public void createCallGraph() {
    createCallGraph(root);
  }

  private void createCallGraph(CGNode node) {
    List<CtAbstractInvocation<?>> invocations = node.getInvocations().stream().filter(inv -> {
      CtExecutable<?> invExe = inv.getExecutable().getDeclaration();
      // TODO handle polymorphism (OverridingMethodFilter)
      return invExe != null && invExe.getBody() != null;
    }).collect(Collectors.toList());
    if (invocations.isEmpty())
      return;

    graph.put(node, new HashSet<>());
    for (var invocation : invocations) {
      CtExecutable<?> invExecutable = invocation.getExecutable().getDeclaration();
      CGNode newNode = new CGNode(invExecutable);
      graph.get(node).add(newNode);
      if (!graph.containsKey(newNode))
        createCallGraph(newNode);
    }
  }

  public void save(String outputPath, String srcPath) {
    Gson gson = new Gson();
    String graphJson = gson.toJson(Mapper.toDto(this, srcPath));
    FileUtils.saveFile(Path.of(outputPath, root.name + ".json"), graphJson);
  }
}
