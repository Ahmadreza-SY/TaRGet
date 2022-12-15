package edu.ahrsy.jparser.entity;

public class SingleHunkTestChange {
  String name;
  String bPath;
  String aPath;
  String bCommit;
  String aCommit;
  Hunk hunk;

  public SingleHunkTestChange(String name, String bPath, String aPath, String bCommit, String aCommit, Hunk hunk) {
    this.name = name;
    this.bPath = bPath;
    this.aPath = aPath;
    this.bCommit = bCommit;
    this.aCommit = aCommit;
    this.hunk = hunk;
  }
}
