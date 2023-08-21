package edu.ahrsy.jparser;

import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class TestMain {

  private static List<CtElement> getElementsByLine(CtType<?> type, List<Integer> lines) {
    return type.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtElement element) {
        if (!element.getPosition().isValidPosition())
          return false;
        return lines.contains(element.getPosition().getLine());
      }
    });
  }

  public static void main(String[] args) {
    // TODO first find change top level type by file then find line elements
    var path = "/home/ahmad/workspace/tc-repair/repair-collection/data-clones/temp/Alluxio/alluxio/codeMining/clone";
    var bSpoon = new Spoon(path, 11);
//    var uniqueTypes = bSpoon.spoon.getModel().getRootPackage().getElements(new AbstractFilter<>() {
//      @Override
//      public boolean matches(CtElement element) {
//        return element.getPosition().isValidPosition();
//      }
//    }).stream().collect(Collectors.groupingBy(e -> e.getClass().getName()))
//        .values().stream().map(group -> group.get(0)).collect(Collectors.toList());
    var changedFile = "dora/core/server/master/src/main/java/alluxio/master/block/meta/WorkerState.java";
    var testFile = "dora/core/server/master/src/test/java/alluxio/master/block/meta/MasterWorkerInfoTest.java";
    ArrayList<Integer> sutLines = new ArrayList<>(Arrays.asList(18, 19, 20));
    ArrayList<Integer> brokenLines = new ArrayList<>(List.of(145));
    var sutElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(changedFile), sutLines);
    var brokenElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(testFile), brokenLines);
    System.out.println(path);
  }
}
