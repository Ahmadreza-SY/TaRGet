package edu.ahrsy.jparser.gumtree;

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
      repairType.addAction(actionType, nodeType, parents);
    }
    return repairType;
  }
}
