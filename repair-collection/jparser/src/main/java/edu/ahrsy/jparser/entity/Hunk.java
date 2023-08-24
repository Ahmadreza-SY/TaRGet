package edu.ahrsy.jparser.entity;

import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Chunk;
import edu.ahrsy.jparser.entity.elements.ElementInfo;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.stream.Collectors;

public class Hunk {
  public List<LineChange> sourceChanges;
  public List<LineChange> targetChanges;
  public ChangeType type;
  public List<ElementInfo> sourceElements;
  public List<ElementInfo> targetElements;

  private static List<LineChange> getLines(Chunk<String> chunk, ChangeType type) {
    var lineChanges = new ArrayList<LineChange>();
    var lines = chunk.getLines();
    for (int i = 0; i < lines.size(); i++) {
      var line = lines.get(i);
      if (!line.isBlank()) lineChanges.add(new LineChange(line, type, chunk.getPosition() + i));
    }
    return lineChanges;
  }

  public static Hunk from(AbstractDelta<String> delta) {
    var hunk = new Hunk();
    switch (delta.getType()) {
      case CHANGE:
        hunk.type = ChangeType.MODIFY;
        hunk.sourceChanges = getLines(delta.getSource(), ChangeType.DELETE);
        hunk.targetChanges = getLines(delta.getTarget(), ChangeType.ADD);
        break;
      case INSERT:
        hunk.type = ChangeType.ADD;
        if (!delta.getSource().getLines().isEmpty())
          throw new RuntimeException("Source of INSERT delta is not empty! " + delta);
        hunk.targetChanges = getLines(delta.getTarget(), ChangeType.ADD);
        break;
      case DELETE:
        hunk.type = ChangeType.DELETE;
        if (!delta.getTarget().getLines().isEmpty())
          throw new RuntimeException("Target of DELETE delta is not empty! " + delta);
        hunk.sourceChanges = getLines(delta.getSource(), ChangeType.DELETE);
        break;
      case EQUAL:
        throw new RuntimeException("No change detected!");
    }
    return hunk;
  }

  public boolean hasSourceChanges() {
    return sourceChanges != null && !sourceChanges.isEmpty();
  }

  public List<Integer> getSourceLineNumbers() {
    if (!hasSourceChanges())
      return Collections.emptyList();
    return sourceChanges.stream().map(c -> c.lineNo).collect(Collectors.toList());
  }

  public boolean hasTargetChanges() {
    return targetChanges != null && !targetChanges.isEmpty();
  }

  public List<Integer> getTargetLineNumbers() {
    if (!hasTargetChanges())
      return Collections.emptyList();
    return targetChanges.stream().map(c -> c.lineNo).collect(Collectors.toList());
  }
}
