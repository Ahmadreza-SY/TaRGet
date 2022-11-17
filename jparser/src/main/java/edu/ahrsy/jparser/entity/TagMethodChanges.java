package edu.ahrsy.jparser.entity;

import java.util.List;

public class TagMethodChanges {
  String baseTag;
  String headTag;
  List<MethodChange> methodChanges;

  public TagMethodChanges(String baseTag, String headTag, List<MethodChange> methodChanges) {
    this.baseTag = baseTag;
    this.headTag = headTag;
    this.methodChanges = methodChanges;
  }
}
