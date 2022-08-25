package edu.ahrsy.jparser.entity;

import com.github.difflib.DiffUtils;
import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Patch;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class MethodChange {
  String filePath;
  String name;
  List<Hunk> hunks;

  public MethodChange(String filePath, String name) {
    this.filePath = filePath;
    this.name = name;
    this.hunks = new ArrayList<>();
  }

  public void extractHunks(String source, String target) {
    List<String> sourceLines = source.isBlank() ? Collections.emptyList() : Arrays.asList(source.split("\n"));
    List<String> targetLines = target.isBlank() ? Collections.emptyList() : Arrays.asList(target.split("\n"));
    Patch<String> patch = DiffUtils.diff(sourceLines, targetLines);
    for (AbstractDelta<String> delta : patch.getDeltas()) {
      hunks.add(Hunk.from(delta));
    }
  }

  public String getName() {
    return name;
  }
}
