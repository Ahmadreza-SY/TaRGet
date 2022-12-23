package edu.ahrsy.jparser.entity;

public class SingleHunkTestChange {
  public String name;
  public TestSource source;
  public String bPath;
  public String aPath;
  public String bCommit;
  public String aCommit;
  public Hunk hunk;

  public SingleHunkTestChange(String name,
          TestSource source,
          String bPath,
          String aPath,
          String bCommit,
          String aCommit,
          Hunk hunk) {
    this.name = name;
    this.source = source;
    this.bPath = bPath;
    this.aPath = aPath;
    this.bCommit = bCommit;
    this.aCommit = aCommit;
    this.hunk = hunk;
  }
}
