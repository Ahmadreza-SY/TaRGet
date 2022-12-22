package edu.ahrsy.jparser.spoon;

import java.util.HashMap;
import java.util.Map;

public class SpoonFactory {
  private static final Map<String, Spoon> spoonInstances = new HashMap<>();

  public static Spoon getOrCreateSpoon(String path, Integer complianceLevel) {
    if (spoonInstances.containsKey(path))
      return spoonInstances.get(path);

    var spoon = new Spoon(path, complianceLevel);
    spoonInstances.put(path, spoon);
    return spoon;
  }
}
