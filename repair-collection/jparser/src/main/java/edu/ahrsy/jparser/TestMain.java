package edu.ahrsy.jparser;

import edu.ahrsy.jparser.entity.elements.ElementInfo;
import edu.ahrsy.jparser.entity.elements.ElementValueHelper;
import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.code.CtConstructorCall;
import spoon.reflect.code.CtFieldRead;
import spoon.reflect.code.CtTypeAccess;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.util.*;
import java.util.stream.Collectors;

public class TestMain {

  private static List<ElementInfo> getElementsByLine(CtType<?> type, List<Integer> lines) {
    return type.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtElement element) {
        if (!element.getPosition().isValidPosition())
          return false;
        return lines.contains(element.getPosition().getLine());
      }
    }).stream().map(TestMain::getElementInfo).filter(e -> e.getValue() != null).collect(Collectors.toList());
  }

  private static ElementInfo getElementInfo(CtElement element) {
    String type = element.getClass().getSimpleName().replace("Impl", "");
    String value = ElementValueHelper.getValue(element);
    return new ElementInfo(type, value);
  }

  private static Map<String, List<ElementInfo>> getSimilarElements(List<ElementInfo> brokenElements,
      List<ElementInfo> sutElements) {
    var result = new HashMap<String, List<ElementInfo>>();
    result.put("equal", new LinkedList<>());
    result.put("similar", new LinkedList<>());
    for (ElementInfo b : brokenElements)
      for (ElementInfo s : sutElements) {
        if (b.equals(s))
          result.get("equal").add(b);
        else if (b.getValue().equals(s.getValue()))
          result.get("similar").add(b);
      }
    return result;
  }

  public static void main(String[] args) {
    var path = "/home/ahmad/workspace/tc-repair/repair-collection/data-clones/temp/Alluxio/alluxio/codeMining/clone";
    var bSpoon = new Spoon(path, 11);
    var changedFile = "dora/core/server/master/src/main/java/alluxio/master/block/meta/WorkerState.java";
    var testFile = "dora/core/server/master/src/test/java/alluxio/master/block/meta/MasterWorkerInfoTest.java";
    ArrayList<Integer> sutLines = new ArrayList<>(Arrays.asList(18, 19, 20));
    ArrayList<Integer> brokenLines = new ArrayList<>(List.of(145));
    var sutElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(changedFile), sutLines);
    var brokenElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(testFile), brokenLines);
    var similarElements = getSimilarElements(brokenElements, sutElements);
    System.out.println(path);
  }
}
