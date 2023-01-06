package edu.ahrsy.jparser.entity;

import com.github.difflib.DiffUtils;
import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Patch;
import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.code.CtComment;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtNamedElement;
import spoon.reflect.visitor.filter.TypeFilter;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class Change {
  String filePath;
  String name;
  List<Hunk> hunks;

  public Change(String filePath, String name) {
    this.filePath = filePath;
    this.name = name;
    this.hunks = new ArrayList<>();
  }

  public void extractHunks(String source, String target) {
    if (source == null || target == null) return;
    List<String> sourceLines = source.isBlank() ? Collections.emptyList() : Arrays.asList(source.split("\n"));
    List<String> targetLines = target.isBlank() ? Collections.emptyList() : Arrays.asList(target.split("\n"));
    Patch<String> patch = DiffUtils.diff(sourceLines, targetLines);
    for (AbstractDelta<String> delta : patch.getDeltas()) {
      hunks.add(Hunk.from(delta));
    }
  }

  public void extractHunks(CtNamedElement source, CtNamedElement target) {
    var sourceCode = source == null ? "" : Spoon.print(source);
    var targetCode = target == null ? "" : Spoon.print(target);
    extractHunks(sourceCode, targetCode);
    applyHunkLineNoOffset(Spoon.getStartLine(source), Spoon.getStartLine(target));
    removeCommentsFromHunks(source, target);
  }

  public void applyHunkLineNoOffset(Integer srcOffset, Integer targetOffset) {
    for (var hunk : this.hunks) {
      if (hunk.sourceChanges != null) for (var sLine : hunk.sourceChanges)
        sLine.lineNo += srcOffset;
      if (hunk.targetChanges != null) for (var tLine : hunk.targetChanges)
        tLine.lineNo += targetOffset;
    }
  }

  public void removeCommentsFromHunks(CtNamedElement source, CtNamedElement target) {
    var sourceCommentLines = Spoon.getCommentsLineNumbers(source);
    var targetCommentLines = Spoon.getCommentsLineNumbers(target);
    if (sourceCommentLines.isEmpty() && targetCommentLines.isEmpty()) return;

    for (var hunk : this.hunks) {
      if (hunk.sourceChanges != null && !sourceCommentLines.isEmpty()) {
        hunk.sourceChanges = hunk.sourceChanges.stream()
                .filter(l -> !sourceCommentLines.contains(l.lineNo))
                .collect(Collectors.toList());
      }
      if (hunk.targetChanges != null && !targetCommentLines.isEmpty()) {
        hunk.targetChanges = hunk.targetChanges.stream()
                .filter(l -> !targetCommentLines.contains(l.lineNo))
                .collect(Collectors.toList());
      }
    }

    // Remove hunks that got empty after removing comments
    this.hunks = this.hunks.stream()
            .filter(h -> !((h.sourceChanges == null || h.sourceChanges.isEmpty()) &&
                    (h.targetChanges == null || h.targetChanges.isEmpty())))
            .collect(Collectors.toList());
  }

  public String getName() {
    return name;
  }

  public List<Hunk> getHunks() {
    return hunks;
  }
}
