package edu.ahrsy.jparser;

import com.github.gumtreediff.tree.Tree;
import gumtree.spoon.AstComparator;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.*;

import java.util.ArrayList;
import java.util.stream.Collectors;

public class GumTree {
  private static CtType<?> getFirstType(String srcPath) {
    SpoonAPI spoon = new Launcher();
    spoon.addInputResource(srcPath);
    spoon.buildModel();
    ArrayList<CtType<?>> orgTypes = (ArrayList<CtType<?>>) spoon.getModel().getAllTypes();
    return orgTypes.get(0);
  }

  public static CtNamedElement getParentMethodOrClass(CtElement element) {
    if (element == null) return null;
    if (element instanceof CtMethod || element instanceof CtClass) return (CtNamedElement) element;

    var methodParent = element.getParent(CtMethod.class);
    if (methodParent != null) return methodParent;

    return element.getParent(CtClass.class);
  }

  public static void main(String[] args) {
    var orgTest = getFirstType("/home/ahmadreza/Desktop/before");
    var modTest = getFirstType("/home/ahmadreza/Desktop/after");
    var diff = new AstComparator().compare(orgTest, modTest);
    for (var op : diff.getAllOperations()) {
      var srcParent = getParentMethodOrClass(op.getSrcNode());
      var srcName = srcParent == null ? null : srcParent.getSimpleName();
      System.out.println("SRC: " + srcName);
      var dstParent = getParentMethodOrClass(op.getDstNode());
      var dstName = dstParent == null ? null : dstParent.getSimpleName();
      System.out.println("DST: " + dstName);
      System.out.println("ACTION PARENTS: " +
              op.getAction().getNode().getParents().stream().map(Tree::getType).collect(Collectors.toList()));
      System.out.println(op.toString().replace("\n", ""));
      System.out.println();
    }
  }
}
