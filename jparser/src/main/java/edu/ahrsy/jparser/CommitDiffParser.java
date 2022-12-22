package edu.ahrsy.jparser;

import edu.ahrsy.jparser.entity.Change;
import edu.ahrsy.jparser.spoon.Spoon;
import org.apache.commons.lang3.tuple.Pair;
import spoon.reflect.declaration.CtExecutable;

import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;

public class CommitDiffParser {
  private final Spoon bSpoon;
  private final Spoon aSpoon;

  public CommitDiffParser(Spoon bSpoon, Spoon aSpoon) {
    this.bSpoon = bSpoon;
    this.aSpoon = aSpoon;
  }

  public List<Change> detectExecutablesChanges(Pair<String, String> changedFile) {
    var bExecutables = bSpoon.getExecutablesByFile(Collections.singleton(changedFile.getLeft()));
    var aExecutables = aSpoon.getExecutablesByFile(Collections.singleton(changedFile.getRight()));

    var commonExecutableChanges = getCommonExecutableChanges(bExecutables, aExecutables);

    var bExecutableNames = bExecutables.stream().map(Spoon::getUniqueName).collect(Collectors.toSet());
    var aExecutableNames = aExecutables.stream().map(Spoon::getUniqueName).collect(Collectors.toSet());
    var missingExecutables = bExecutables.stream()
            .filter(bm -> !aExecutableNames.contains(Spoon.getUniqueName(bm)))
            .collect(Collectors.toList());
    var newExecutables = aExecutables.stream()
            .filter(am -> !bExecutableNames.contains(Spoon.getUniqueName(am)))
            .collect(Collectors.toList());
    var missingExecutablesChanges = detectMissingExecutablesChanges(missingExecutables, newExecutables);

    return Stream.concat(commonExecutableChanges.stream(), missingExecutablesChanges.stream())
            .collect(Collectors.toList());
  }

  private List<Change> getCommonExecutableChanges(List<CtExecutable<?>> bExecutables,
          List<CtExecutable<?>> aExecutables) {
    var bExecutablesMap = bExecutables.stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m));
    var changes = new ArrayList<Change>();
    for (var aExecutable : aExecutables) {
      var aExecutableName = Spoon.getUniqueName(aExecutable);
      if (!bExecutablesMap.containsKey(aExecutableName)) continue;

      var bExecutable = bExecutablesMap.get(aExecutableName);
      if (!Spoon.codeIsModified(bExecutable, aExecutable)) continue;

      var path = Spoon.getRelativePath(aExecutable, aSpoon.srcPath);
      var change = new Change(path, aExecutableName);
      change.extractHunks(bExecutable, aExecutable);
      changes.add(change);
    }
    return changes;
  }

  private List<Change> detectMissingExecutablesChanges(List<CtExecutable<?>> missingExecutables,
          List<CtExecutable<?>> newExecutables) {
    var executableChanges = new ArrayList<Change>();

    // If no new executables are added, the missing executable is deleted
    if (newExecutables.isEmpty()) {
      for (var missingExecutable : missingExecutables) {
        var path = Spoon.getRelativePath(missingExecutable, bSpoon.srcPath);
        var change = new Change(path, Spoon.getUniqueName(missingExecutable));
        change.extractHunks(Spoon.print(missingExecutable), "");
        change.applyHunkLineNoOffset(Spoon.getStartLine(missingExecutable), 0);
        executableChanges.add(change);
      }
      return executableChanges;
    }

    for (var missingExecutable : missingExecutables) {
      var missingExecutableFile = Spoon.getRelativePath(missingExecutable, bSpoon.srcPath);
      CtExecutable<?> mostSimilarExecutable = null;
      double maxSimilarity = -1;
      for (var newExecutable : newExecutables) {
        var newExecutableFile = Spoon.getRelativePath(newExecutable, aSpoon.srcPath);
        // missing executable and new executable should be in the same file
        if (!missingExecutableFile.equals(newExecutableFile)) continue;
        // missing executable and new executable should be both the same type (both constructors or methods)
        if (missingExecutable.getClass() != newExecutable.getClass()) continue;

        var similarity = SimilarityChecker.computeOverallSimilarity(missingExecutable, newExecutable);
        if (similarity > maxSimilarity) {
          mostSimilarExecutable = newExecutable;
          maxSimilarity = similarity;
        }
      }

      var executableChange = new Change(missingExecutableFile, Spoon.getUniqueName(missingExecutable));
      // If the most similar executable has higher similarity than the threshold, it's matched
      if (maxSimilarity > SimilarityChecker.SIM_THRESHOLD) {
        executableChange.extractHunks(missingExecutable, mostSimilarExecutable);
      }
      // Otherwise, the missing executable is deleted
      else {
        executableChange.extractHunks(Spoon.print(missingExecutable), "");
        executableChange.applyHunkLineNoOffset(Spoon.getStartLine(missingExecutable), 0);
      }
      executableChanges.add(executableChange);
    }

    return executableChanges;
  }

  public Change detectClassChanges(Pair<String, String> changedFile) {
    var bClass = bSpoon.getTopLevelTypeByFile(changedFile.getLeft());
    var aClass = aSpoon.getTopLevelTypeByFile(changedFile.getRight());

    if (!Spoon.codeIsModified(aClass, bClass)) return null;

    var path = Spoon.getRelativePath(aClass, aSpoon.srcPath);
    var change = new Change(path, aClass.getQualifiedName());
    change.extractHunks(bClass, aClass);
    return change;
  }
}
