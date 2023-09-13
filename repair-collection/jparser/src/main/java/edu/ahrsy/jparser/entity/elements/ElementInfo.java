package edu.ahrsy.jparser.entity.elements;

public class ElementInfo {
  String type;
  String value;

  public ElementInfo(String type, String value) {
    this.type = type;
    this.value = value;
  }

  public String getType() {
    return type;
  }

  public String getValue() {
    return value;
  }

  @Override
  public boolean equals(Object obj) {
    if (this == obj)
      return true;
    if (!(obj instanceof ElementInfo))
      return false;
    var cObj = (ElementInfo) obj;
    return type.equals(cObj.getType()) && value.equals(cObj.getValue());
  }

  @Override
  public String toString() {
    return "ElementInfo(" +
        "type='" + type + '\'' +
        ", value='" + value + '\'' +
        ')';
  }
}
