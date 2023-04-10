package edu.ahrsy.jparser.refactoringminer;

import java.util.List;

public class RefactoringInfo {
  public String sourceFile;
  public String refactoringType;
  public List<Integer> bLines;

  public RefactoringInfo(String sourceFile, String refactoringType, List<Integer> bLines) {
    this.sourceFile = sourceFile;
    this.refactoringType = refactoringType;
    this.bLines = bLines;
  }
}
