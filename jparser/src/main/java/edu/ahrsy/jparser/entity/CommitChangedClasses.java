package edu.ahrsy.jparser.entity;

import org.apache.commons.lang3.tuple.ImmutablePair;

import java.util.List;

public class CommitChangedClasses {
  public String bCommit;
  public String aCommit;
  public List<ImmutablePair<String, String>> changedClasses;
}
