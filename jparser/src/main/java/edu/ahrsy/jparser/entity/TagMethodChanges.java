package edu.ahrsy.jparser.entity;

import java.util.List;

public class TagMethodChanges {
  String baseTag;
  String headTag;
  List<Change> changes;

  public TagMethodChanges(String baseTag, String headTag, List<Change> changes) {
    this.baseTag = baseTag;
    this.headTag = headTag;
    this.changes = changes;
  }
}
