package edu.ahrsy.jparser.entity.elements;

import com.opencsv.bean.CsvBindByName;

public class SampleTest {
  @CsvBindByName(column = "ID")
  public String id;
  @CsvBindByName(column = "Class")
  public String className;
  @CsvBindByName(column = "Test")
  public String testName;
  @CsvBindByName(column = "Commit Link")
  public String commitLink;
}
