package edu.ahrsy.jparser.graph.dto;

import java.util.HashMap;
import java.util.concurrent.atomic.AtomicInteger;

public class IdGenerator {
  private final AtomicInteger idCounter = new AtomicInteger(0);
  private final HashMap<String, Integer> uIdMap = new HashMap<>();

  public Integer getId(String uId) {
    if (uIdMap.containsKey(uId))
      return uIdMap.get(uId);
    var newId = idCounter.getAndIncrement();
    uIdMap.put(uId, newId);
    return newId;
  }
}
