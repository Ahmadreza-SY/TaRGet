package edu.ahrsy.jparser.refactoringMiner;

import org.refactoringminer.api.RefactoringType;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class MethodRefactoring {
  String method;
  List<RefactoringCommit> refactoringCommits;

  public MethodRefactoring(String method) {
    this.method = method;
    this.refactoringCommits = new ArrayList<>();
  }

  public void addRefactoring(String commitId, RefactoringType refactoringType) {
    RefactoringCommit refactoringCommit;
    var found = refactoringCommits.stream().filter(rc -> rc.commitId.equals(commitId)).collect(Collectors.toList());
    if (found.isEmpty()) {
      refactoringCommit = new RefactoringCommit(commitId);
      refactoringCommits.add(refactoringCommit);
    } else
      refactoringCommit = found.get(0);

    refactoringCommit.addRefactoring(refactoringType);
  }

  @Override
  public int hashCode() {
    return method.hashCode();
  }

  @Override
  public boolean equals(Object obj) {
    if (this == obj) return true;
    if (obj == null || getClass() != obj.getClass()) return false;

    MethodRefactoring methodRefactoring = (MethodRefactoring) obj;
    return method.equals(methodRefactoring.method);
  }

  static class RefactoringCommit {
    String commitId;
    List<RefactoringType> refactorings;

    public RefactoringCommit(String commitId) {
      this.commitId = commitId;
      this.refactorings = new ArrayList<>();
    }

    public void addRefactoring(RefactoringType refactoringType) {
      refactorings.add(refactoringType);
    }
  }
}
