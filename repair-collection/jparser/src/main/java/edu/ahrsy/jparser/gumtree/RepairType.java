package edu.ahrsy.jparser.gumtree;


import java.util.ArrayList;
import java.util.List;

public class RepairType {
  public String repairId;
  public List<ActionType> actions;

  class ActionType {
    public String actionType;
    public String nodeType;
    public List<String> parents;

    public ActionType(String actionType, String nodeType, List<String> parents) {
      this.actionType = actionType;
      this.nodeType = nodeType;
      this.parents = parents;
    }
  }

  public RepairType(String repairId) {
    this.repairId = repairId;
    this.actions = new ArrayList<>();
  }

  public void addAction(String actionType, String nodeType, List<String> parents) {
    this.actions.add(new ActionType(actionType, nodeType, parents));
  }
}
