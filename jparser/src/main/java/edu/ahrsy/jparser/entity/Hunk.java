package edu.ahrsy.jparser.entity;

import com.github.difflib.patch.AbstractDelta;

import java.util.List;
import java.util.stream.Collectors;

public class Hunk {
  public List<LineChange> sourceChanges;
  public List<LineChange> targetChanges;
  public ChangeType type;

  public static Hunk from(AbstractDelta<String> delta) {
    var hunk = new Hunk();
    switch (delta.getType()) {
      case CHANGE:
        hunk.type = ChangeType.MODIFY;
        hunk.sourceChanges = delta.getSource()
                .getLines()
                .stream()
                .map(l -> new LineChange(l, ChangeType.DELETE))
                .collect(Collectors.toList());
        hunk.targetChanges = delta.getTarget()
                .getLines()
                .stream()
                .map(l -> new LineChange(l, ChangeType.ADD))
                .collect(Collectors.toList());
        break;
      case INSERT:
        hunk.type = ChangeType.ADD;
        if (!delta.getSource().getLines().isEmpty())
          throw new RuntimeException("Source of INSERT delta is not empty! " + delta);
        hunk.targetChanges = delta.getTarget()
                .getLines()
                .stream()
                .map(l -> new LineChange(l, ChangeType.ADD))
                .collect(Collectors.toList());
        break;
      case DELETE:
        hunk.type = ChangeType.DELETE;
        if (!delta.getTarget().getLines().isEmpty())
          throw new RuntimeException("Target of DELETE delta is not empty! " + delta);
        hunk.sourceChanges = delta.getSource()
                .getLines()
                .stream()
                .map(l -> new LineChange(l, ChangeType.DELETE))
                .collect(Collectors.toList());
        break;
    }
    return hunk;
  }
}
