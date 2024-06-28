package edu.ahrsy.jparser.entity;

import edu.ahrsy.jparser.gumtree.Action;
import org.refactoringminer.api.RefactoringType;

import java.util.List;

public class SingleHunkTestChange {
  public String name;
  public TestSource bSource;
  public TestSource aSource;
  public String bPath;
  public String aPath;
  public String bCommit;
  public String aCommit;
  public List<Hunk> hunks;
  public List<Action> astActions;
  public List<RefactoringType> refactorings;
  public Boolean onlyTestsChanged;

  public SingleHunkTestChange(String name,
                              TestSource bSource,
                              TestSource aSource,
                              String bPath,
                              String aPath,
                              String bCommit,
                              String aCommit,
                              List<Hunk> hunks,
                              List<Action> astActions,
                              List<RefactoringType> refactorings,
                              Boolean onlyTestsChanged) {
    this.name = name;
    this.bSource = bSource;
    this.aSource = aSource;
    this.bPath = bPath;
    this.aPath = aPath;
    this.bCommit = bCommit;
    this.aCommit = aCommit;
    this.hunks = hunks;
    this.astActions = astActions;
    this.refactorings = refactorings;
    this.onlyTestsChanged = onlyTestsChanged;
  }
}
