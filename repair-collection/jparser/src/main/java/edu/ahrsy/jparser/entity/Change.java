package edu.ahrsy.jparser.entity;

import com.github.difflib.DiffUtils;
import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Patch;
import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.declaration.CtNamedElement;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class Change {
  String bPath;
  String aPath;
  String name;
  List<Hunk> hunks;

  public Change(String bPath, String aPath, String name) {
    this.bPath = bPath;
    this.aPath = aPath;
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
    if (!Spoon.codeIsModified(source, target))
      return;
    var sourceCode = source == null ? "" : Spoon.print(source);
    var targetCode = target == null ? "" : Spoon.print(target);
    extractHunks(sourceCode, targetCode);
    applyHunkLineNoOffset(Spoon.getStartLine(source), Spoon.getStartLine(target));
    extractElements(source, target);
  }

  private void extractElements(CtNamedElement source, CtNamedElement target) {
    for (var hunk : this.hunks) {
      if (source != null)
        hunk.sourceElements = Spoon.getElementsByLine(source, hunk.getSourceLineNumbers());
      if (target != null)
        hunk.targetElements = Spoon.getElementsByLine(target, hunk.getTargetLineNumbers());
    }
  }

  public void applyHunkLineNoOffset(Integer srcOffset, Integer targetOffset) {
    for (var hunk : this.hunks) {
      if (hunk.sourceChanges != null) for (var sLine : hunk.sourceChanges)
        sLine.lineNo += srcOffset;
      if (hunk.targetChanges != null) for (var tLine : hunk.targetChanges)
        tLine.lineNo += targetOffset;
    }
  }

  public String getName() {
    return name;
  }

  public String getBPath() {
    return bPath;
  }

  public List<Hunk> getHunks() {
    return hunks;
  }
}
