package edu.ahrsy.jparser.gumtree;

import com.github.gumtreediff.tree.Tree;
import edu.ahrsy.jparser.cli.CommandDiff;
import edu.ahrsy.jparser.spoon.Spoon;
import gumtree.spoon.AstComparator;
import spoon.reflect.declaration.CtElement;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

public class GumTreeUtils {
  public static RepairType getRepairType(RepairPatch repairPatch, Integer complianceLevel) {
    var bSpoon = new Spoon(repairPatch.beforePath, complianceLevel);
    var aSpoon = new Spoon(repairPatch.afterPath, complianceLevel);
    var bType = bSpoon.getTopLevelType();
    var aType = aSpoon.getTopLevelType();
    var astActions = getASTActions(bType, aType);
    var repairType = new RepairType(repairPatch.repairId);
    repairType.actions.addAll(astActions);
    return repairType;
  }

  public static List<Action> getASTActions(CtElement before, CtElement after) {
    var diff = new AstComparator().compare(before, after);
    var rootOperations = diff.getRootOperations();
    var actions = new ArrayList<Action>();
    for (var op : rootOperations) {
      var actionType = op.getAction().getClass().getSimpleName();
      var nodeType = op.getAction().getNode().getType().name;
      var parents = op.getAction()
          .getNode()
          .getParents()
          .stream().map(p -> p.getType().name)
          .collect(Collectors.toList());

      var action = new Action(actionType, nodeType, parents);
      if (op.getSrcNode() != null && op.getSrcNode().getMetadata("gtnode") != null)
        action.srcNode = Node.from((Tree) op.getSrcNode().getMetadata("gtnode"));
      if (op.getDstNode() != null && op.getDstNode().getMetadata("gtnode") != null)
        action.dstNode = Node.from((Tree) op.getDstNode().getMetadata("gtnode"));

      if (action.srcNode == null && action.dstNode == null && rootOperations.size() > 1)
        continue;
      actions.add(action);
    }
    return actions;
  }
}
