package edu.ahrsy.jparser.gumtree;

import java.util.List;

public class Action {
  public String type;
  public String nodeType;
  public List<String> parents;
  public Node srcNode;
  public Node dstNode;

  public Action(String type, String nodeType, List<String> parents) {
    this.type = type;
    this.nodeType = nodeType;
    this.parents = parents;
  }
}
