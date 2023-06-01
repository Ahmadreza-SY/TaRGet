package edu.ahrsy.jparser.graph;

import edu.ahrsy.jparser.graph.dto.CallGraphDTO;
import edu.ahrsy.jparser.graph.dto.Mapper;
import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.declaration.CtExecutable;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class CallGraph {
  public final Spoon spoon;
  public Map<CGNode, HashSet<CGNode>> graph;
  public CGNode root;

  public CallGraph(CtExecutable<?> root, Spoon spoon) {
    this.graph = new HashMap<>();
    this.root = new CGNode(root);
    this.graph.put(this.root, new HashSet<>());
    this.spoon = spoon;
  }

  public void createCallGraph() {
    createCallGraph(root);
  }

  private void createCallGraph(CGNode node) {
    List<CtAbstractInvocation<?>> invocations = node.getInvocations().stream().filter(inv -> {
      CtExecutable<?> invExe = inv.getExecutable().getDeclaration();
      // TODO handle polymorphism (OverridingMethodFilter)
      return invExe != null && invExe.getBody() != null && Spoon.isMethodOrConstructor(invExe);
    }).collect(Collectors.toList());
    if (invocations.isEmpty()) return;

    graph.put(node, new HashSet<>());
    for (var invocation : invocations) {
      CtExecutable<?> invExecutable = invocation.getExecutable().getDeclaration();
      CGNode newNode = new CGNode(invExecutable);
      graph.get(node).add(newNode);
      if (!graph.containsKey(newNode)) createCallGraph(newNode);
    }
  }

  public CallGraphDTO toDTO(String srcPath) {
    return Mapper.toDto(this, srcPath);
  }
}
