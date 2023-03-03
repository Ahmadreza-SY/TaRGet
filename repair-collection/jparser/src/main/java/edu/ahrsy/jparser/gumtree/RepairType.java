package edu.ahrsy.jparser.gumtree;


import java.util.ArrayList;
import java.util.List;

public class RepairType {
  public String repairId;
  public List<Action> actions;

  public RepairType(String repairId) {
    this.repairId = repairId;
    this.actions = new ArrayList<>();
  }
}
