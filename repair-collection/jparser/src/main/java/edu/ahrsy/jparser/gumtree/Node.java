package edu.ahrsy.jparser.gumtree;

import com.github.gumtreediff.tree.Tree;

public class Node {
  public String label;
  public Integer childCount;

  public static Node from(Tree tree) {
    return new Node(tree.getLabel(), tree.getChildren().size());
  }

  public Node(String label, Integer childCount) {
    this.label = label;
    this.childCount = childCount;
  }
}
