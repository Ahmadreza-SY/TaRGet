package edu.ahrsy.jparser.entity;

import java.util.ArrayList;
import java.util.List;

public class CommitChanges {
  String bCommit;
  String aCommit;
  List<Change> changes;

  public CommitChanges(String bCommit, String aCommit) {
    this.bCommit = bCommit;
    this.aCommit = aCommit;
    this.changes = new ArrayList<>();
  }

  public void addChanges(List<Change> changes) {
    this.changes.addAll(changes);
  }

  public String getBCommit() {
    return bCommit;
  }

  public String getACommit() {
    return aCommit;
  }

  public List<Change> getChanges() {
    return changes;
  }
}
