package edu.ahrsy.jparser.entity;

public class LineChange {
  String line;
  ChangeType type;

  public LineChange(String line, ChangeType type) {
    this.line = line;
    this.type = type;
  }
}