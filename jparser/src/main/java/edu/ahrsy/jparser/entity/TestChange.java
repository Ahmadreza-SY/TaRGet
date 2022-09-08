package edu.ahrsy.jparser.entity;

import java.util.List;

public class TestChange {
  String name;
  String baseTag;
  String headTag;
  List<Hunk> hunks;

  public TestChange(String name, String baseTag, String headTag, List<Hunk> hunks) {
    this.name = name;
    this.baseTag = baseTag;
    this.headTag = headTag;
    this.hunks = hunks;
  }
}
