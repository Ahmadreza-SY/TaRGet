package edu.ahrsy.jparser.entity;

import com.google.gson.annotations.SerializedName;

import java.util.List;

public class TestChangeCoverage {
  public String test;
  public String baseTag;
  public String headTag;
  @SerializedName("covered_changed_files")
  public List<String> coveredChangedFiles;
}
