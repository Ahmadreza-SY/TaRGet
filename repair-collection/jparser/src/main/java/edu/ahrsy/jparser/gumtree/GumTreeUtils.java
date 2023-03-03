package edu.ahrsy.jparser.gumtree;

import com.github.gumtreediff.tree.Tree;
import edu.ahrsy.jparser.cli.CommandDiff;
import edu.ahrsy.jparser.spoon.Spoon;
import gumtree.spoon.AstComparator;

import java.util.stream.Collectors;

public class GumTreeUtils {
  public static RepairType getRepairType(RepairPatch repairPatch, Integer complianceLevel) {
    var bSpoon = new Spoon(repairPatch.beforePath, complianceLevel);
    var aSpoon = new Spoon(repairPatch.afterPath, complianceLevel);
    var bType = bSpoon.getTopLevelType();
    var aType = aSpoon.getTopLevelType();
    var diff = new AstComparator().compare(bType, aType);
    var repairType = new RepairType(repairPatch.repairId);
    for (var op : diff.getRootOperations()) {
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

      repairType.actions.add(action);
    }
    return repairType;
  }
}
