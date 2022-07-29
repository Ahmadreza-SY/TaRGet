package edu.ahrsy.jparser.entity;

import java.util.ArrayList;
import java.util.List;

public class MethodChange {
  String filePath;
  String name;
  List<Hunk> hunks;

  public MethodChange(String filePath, String name) {
    this.filePath = filePath;
    this.name = name;
    this.hunks = new ArrayList<>();
  }

  public void addHunk(Hunk hunk) {
    hunks.add(hunk);
  }
}
