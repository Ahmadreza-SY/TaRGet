package edu.ahrsy.jparser.entity;

import com.opencsv.bean.CsvBindByName;

public class TestRepair {
  @CsvBindByName(column = "class")
  public String _class;
  @CsvBindByName(column = "method")
  public String method;
  @CsvBindByName(column = "path")
  public String path;
  @CsvBindByName(column = "base_tag")
  public String baseTag;
  @CsvBindByName(column = "head_tag")
  public String headTag;

  public String getMethodSignature() {
    return _class + "." + method;
  }

  public String getPath() {
    return path;
  }
}
