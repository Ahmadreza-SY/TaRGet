package edu.ahrsy.jparser.entity;

import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Chunk;

import java.util.List;
import java.util.stream.Collectors;

public class Hunk {
  public List<LineChange> sourceChanges;
  public List<LineChange> targetChanges;
  public ChangeType type;

  private static List<LineChange> getLines(Chunk<String> chunk, ChangeType type) {
    return chunk.getLines()
            .stream()
            .map(l -> new LineChange(l, type))
            .filter(l -> !l.line.isBlank())
            .collect(Collectors.toList());
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
}
