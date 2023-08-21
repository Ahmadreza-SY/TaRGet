package edu.ahrsy.jparser.entity;

public class ElementInfo {
  String type;
  String value;

  public ElementInfo(String type, String value) {
    this.type = type;
    this.value = value;
  }

  public String getValue() {
    return value;
  }

  @Override
  public String toString() {
    return "ElementInfo{" +
        "type='" + type + '\'' +
        ", value='" + value + '\'' +
        '}';
  }
}
