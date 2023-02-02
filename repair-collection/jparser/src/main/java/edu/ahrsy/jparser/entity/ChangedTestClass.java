package edu.ahrsy.jparser.entity;

import com.opencsv.bean.CsvBindByName;

public class ChangedTestClass {
  @CsvBindByName(column = "b_path")
  public String beforePath;
  @CsvBindByName(column = "a_path")
  public String afterPath;
  @CsvBindByName(column = "b_commit")
  public String beforeCommit;
  @CsvBindByName(column = "a_commit")
  public String afterCommit;
}
