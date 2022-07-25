package edu.ahrsy.jparser.graph;

import spoon.reflect.code.CtAbstractInvocation;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.io.File;
import java.util.List;

public class CGNode {
  CtExecutable<?> executable;
  public String name;

  public CGNode(CtExecutable<?> executable) {
    this.executable = executable;
    this.name = generateName(executable);
  }

  private static String generateName(CtExecutable<?> executable) {
    if (executable instanceof CtConstructor<?>)
      return executable.getSignature();
    return String.format("%s.%s", ((CtType<?>) executable.getParent()).getQualifiedName(), executable.getSignature());
  }

  public List<CtAbstractInvocation<?>> getInvocations() {
    return executable.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtAbstractInvocation<?> element) {
        return super.matches(element);
      }
    });
  }

  public String getRelativePath(String srcPath) {
    var srcURI = new File(srcPath).toURI();
    var absFile = executable.getPosition().getCompilationUnit().getFile();
    return srcURI.relativize(absFile.toURI()).getPath();
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
