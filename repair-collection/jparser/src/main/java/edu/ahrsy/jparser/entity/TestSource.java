package edu.ahrsy.jparser.entity;

import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.declaration.CtMethod;

public class TestSource {
  public Integer startLine;
  public String code;

  public TestSource(Integer startLine, String code) {
    this.startLine = startLine;
    this.code = code;
  }

  public static TestSource from(CtMethod<?> method) {
    return new TestSource(Spoon.getStartLine(method), Spoon.print(method));
  }
}
