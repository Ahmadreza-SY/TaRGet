package edu.ahrsy.jparser.graph;

import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.util.List;

public class CGNode {
  public String name;
  public CtExecutable<?> executable;

  public CGNode(CtExecutable<?> executable) {
    this.executable = executable;
    this.name = Spoon.getUniqueName(executable);
  }

  public List<CtAbstractInvocation<?>> getInvocations() {
    return executable.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtAbstractInvocation<?> element) {
        return super.matches(element);
      }
    });
  }

  @Override
  public boolean equals(Object obj) {
    if (this == obj)
      return true;
    if (obj == null || getClass() != obj.getClass())
      return false;

    CGNode node = (CGNode) obj;
    return name.equals(node.name);
  }

  @Override
  public int hashCode() {
    return name.hashCode();
  }
}
