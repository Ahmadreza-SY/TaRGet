package edu.ahrsy.jparser.gumtree;

import com.opencsv.bean.CsvBindByName;

public class RepairPatch {
  @CsvBindByName(column = "id")
  public String repairId;
  @CsvBindByName(column = "before_path")
  public String beforePath;
  @CsvBindByName(column = "after_path")
  public String afterPath;
}
