package edu.ahrsy.jparser.entity;

import edu.ahrsy.jparser.gumtree.Action;

import java.util.List;

public class SingleHunkTestChange {
  public String name;
  public TestSource bSource;
  public TestSource aSource;
  public String bPath;
  public String aPath;
  public String bCommit;
  public String aCommit;
  public Hunk hunk;
  public List<Action> astActions;

  public SingleHunkTestChange(String name,
      TestSource bSource,
      TestSource aSource,
      String bPath,
      String aPath,
      String bCommit,
      String aCommit,
      Hunk hunk,
      List<Action> astActions) {
    this.name = name;
    this.bSource = bSource;
    this.aSource = aSource;
    this.bPath = bPath;
    this.aPath = aPath;
    this.bCommit = bCommit;
    this.aCommit = aCommit;
    this.hunk = hunk;
    this.astActions = astActions;
  }
}
