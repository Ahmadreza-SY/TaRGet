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

    var bExecutableNames = bExecutables.stream().map(this::getExecutableLocalName).collect(Collectors.toSet());
    var aExecutableNames = aExecutables.stream().map(this::getExecutableLocalName).collect(Collectors.toSet());
    var missingExecutables = bExecutables.stream()
            .filter(bm -> !aExecutableNames.contains(getExecutableLocalName(bm)))
            .collect(Collectors.toList());
    var newExecutables = aExecutables.stream()
            .filter(am -> !bExecutableNames.contains(getExecutableLocalName(am)))
            .collect(Collectors.toList());
    var missingExecutablesChanges = detectMissingExecutablesChanges(missingExecutables, newExecutables);

    return Stream.concat(commonExecutableChanges.stream(), missingExecutablesChanges.stream())
            .collect(Collectors.toList());
  }

  private String getExecutableLocalName(CtExecutable<?> executable) {
    var parentName = Spoon.getParentQualifiedName(executable);
    var items = parentName.split("\\$");
    var simpleSignature = Spoon.getSimpleSignature(executable);
    if (items.length == 1) return simpleSignature;
    return String.format("%s.%s", String.join(".", Arrays.copyOfRange(items, 1, items.length)), simpleSignature);
  }

  private List<Change> getCommonExecutableChanges(List<CtExecutable<?>> bExecutables,
          List<CtExecutable<?>> aExecutables) {
    var bExecutablesMap = bExecutables.stream().collect(Collectors.toMap(this::getExecutableLocalName, m -> m));
    var changes = new ArrayList<Change>();
    for (var aExecutable : aExecutables) {
      var aExecutableName = getExecutableLocalName(aExecutable);
      if (!bExecutablesMap.containsKey(aExecutableName)) continue;

      var bExecutable = bExecutablesMap.get(aExecutableName);
      if (!Spoon.codeIsModified(bExecutable, aExecutable)) continue;

      var path = Spoon.getRelativePath(bExecutable, bSpoon.srcPath);
      var change = new Change(path, Spoon.getUniqueName(bExecutable));
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
        change.extractHunks(missingExecutable, null);
        executableChanges.add(change);
      }
      return executableChanges;
    }

    for (var missingExecutable : missingExecutables) {
      var missingExecutableFile = Spoon.getRelativePath(missingExecutable, bSpoon.srcPath);
      CtExecutable<?> mostSimilarExecutable = null;
      double maxSimilarity = -1;
      for (var newExecutable : newExecutables) {
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
        executableChange.extractHunks(missingExecutable, null);
      }
      executableChanges.add(executableChange);
    }

    return executableChanges;
  }

  public Change detectClassChanges(Pair<String, String> changedFile) {
    var bClass = bSpoon.getTopLevelTypeByFile(changedFile.getLeft());
    var aClass = aSpoon.getTopLevelTypeByFile(changedFile.getRight());

    if (!Spoon.codeIsModified(aClass, bClass)) return null;

    var path = Spoon.getRelativePath(bClass, bSpoon.srcPath);
    var change = new Change(path, bClass.getQualifiedName());
    change.extractHunks(bClass, aClass);
    return change;
  }
}
