package edu.ahrsy.jparser.refactoringminer;

public class RenameRefactoring {
  public String refactoringType;
  public String originalName;
  public String newName;

  public RenameRefactoring(String refactoringType, String originalName, String newName) {
    this.refactoringType = refactoringType;
    this.originalName = originalName;
    this.newName = newName;
  }
}
