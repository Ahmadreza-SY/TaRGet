package edu.ahrsy.jparser.entity;

public class LineChange {
  String line;
  ChangeType type;
  Integer lineNo;

  public LineChange(String line, ChangeType type, Integer lineNo) {
    this.line = line.strip();
    this.type = type;
    this.lineNo = lineNo;
  }
}
