package edu.ahrsy.jparser.entity;

import java.util.List;

public class ReleaseMethodChanges {
  String baseTag;
  String headTag;
  List<MethodChange> methodChanges;

  public ReleaseMethodChanges(String baseTag, String headTag, List<MethodChange> methodChanges) {
    this.baseTag = baseTag;
    this.headTag = headTag;
    this.methodChanges = methodChanges;
  }
}
