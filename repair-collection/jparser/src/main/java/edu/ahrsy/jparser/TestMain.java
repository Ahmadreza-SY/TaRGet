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

  private static ElementInfo getElementInfo(CtElement element) {
    String type = element.getClass().getSimpleName().replace("Impl", "");
    String value = ElementValueHelper.getValue(element);
    return new ElementInfo(type, value);
  }

  public static void main(String[] args) {
    // TODO first find change top level type by file then find line elements
    var path = "/home/ahmad/workspace/tc-repair/repair-collection/data-clones/temp/Alluxio/alluxio/codeMining/clone";
    var bSpoon = new Spoon(path, 11);
    var uniqueTypes = bSpoon.spoon.getModel().getRootPackage().getElements(new AbstractFilter<>() {
          @Override
          public boolean matches(CtElement element) {
            return element.getPosition().isValidPosition();
          }
        }).stream().map(TestMain::getElementInfo).filter(e -> e.getValue() != null)
        .collect(Collectors.groupingBy(ElementInfo::getType));
    var uniqueValues = uniqueTypes.entrySet().stream()
        .collect(Collectors.toMap(Map.Entry::getKey,
            entry -> entry.getValue().stream().map(ElementInfo::getValue).distinct().collect(Collectors.toList())));

    Map<String, List<String>> intersectionMap = new HashMap<>();
    List<String> keys = new ArrayList<>(uniqueValues.keySet());
    // Generate combinations of key pairs
    for (int i = 0; i < keys.size(); i++) {
      for (int j = i + 1; j < keys.size(); j++) {
        String key1 = keys.get(i);
        String key2 = keys.get(j);
        List<String> intersection = uniqueValues.get(key1).stream()
            .filter(uniqueValues.get(key2)::contains)
            .collect(Collectors.toList());
        if (!intersection.isEmpty())
          intersectionMap.put(String.format("%s,%s", key1, key2), intersection);
      }
    }
    intersectionMap = intersectionMap.entrySet().stream()
        .sorted(Comparator.comparingInt(entry -> entry.getValue().size()))
        .collect(Collectors.toMap(
            Map.Entry::getKey,
            Map.Entry::getValue,
            (e1, e2) -> e1,
            LinkedHashMap::new
        ));
//    var changedFile = "dora/core/server/master/src/main/java/alluxio/master/block/meta/WorkerState.java";
//    var testFile = "dora/core/server/master/src/test/java/alluxio/master/block/meta/MasterWorkerInfoTest.java";
//    ArrayList<Integer> sutLines = new ArrayList<>(Arrays.asList(18, 19, 20));
//    ArrayList<Integer> brokenLines = new ArrayList<>(List.of(145));
//    var sutElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(changedFile), sutLines);
//    var brokenElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(testFile), brokenLines);
    System.out.println(path);
  }
}
