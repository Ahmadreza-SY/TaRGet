package edu.ahrsy.jparser;

import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class CallGraph {
  Map<String, HashSet<String>> callGraph;

  public CallGraph() {
    this.callGraph = new HashMap<>();
  }

  private static String getNodeName(CtExecutable<?> executable) {
    if (executable instanceof CtConstructor<?>)
      return executable.getSignature();
    return String.format("%s.%s", ((CtType<?>) executable.getParent()).getQualifiedName(), executable.getSignature());
  }

  private static List<CtAbstractInvocation<?>> getInvocations(CtExecutable<?> executable) {
    return executable.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtAbstractInvocation<?> element) {
        return super.matches(element);
      }
    });
  }

  public void createCallGraph(CtExecutable<?> executable) {
    String uniqueName = getNodeName(executable);
    List<CtAbstractInvocation<?>> invocations = getInvocations(executable).stream().filter(inv -> {
      CtExecutable<?> invExe = inv.getExecutable().getDeclaration();
      // TODO handle polymorphism
      return invExe != null && invExe.getBody() != null;
    }).collect(Collectors.toList());
    if (invocations.isEmpty())
      return;

    callGraph.put(uniqueName, new HashSet<>());
    for (var invocation : invocations) {
      CtExecutable<?> invExecutable = invocation.getExecutable().getDeclaration();
      String invUniqueName = getNodeName(invExecutable);
      callGraph.get(uniqueName).add(invUniqueName);
      if (!callGraph.containsKey(invUniqueName))
        createCallGraph(invExecutable);
    }
  }

  // TODO handle polymorphism
  /*private static List<CtMethod<?>> getOverrides(CtMethod<?> method) {
    return spoon.getModel().getRootPackage().getElements(new OverridingMethodFilter(method));
  }*/
}
