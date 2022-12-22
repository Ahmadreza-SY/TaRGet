package edu.ahrsy.jparser.entity;

import com.github.difflib.DiffUtils;
import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Patch;
import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtNamedElement;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

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
    var sourceCode = Spoon.print(source);
    var targetCode = Spoon.print(target);
    extractHunks(sourceCode, targetCode);
    applyHunkLineNoOffset(Spoon.getStartLine(source), Spoon.getStartLine(target));
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

  public List<Hunk> getHunks() {
    return hunks;
  }
}
