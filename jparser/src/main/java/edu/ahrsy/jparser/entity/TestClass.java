package edu.ahrsy.jparser.entity;

public class TestClass {
  public String name;
  public String path;

  public TestClass(String name, String path) {
    this.name = name;
    this.path = path;
  }

  @Override
  public String toString() {
    return name;
  }
}
