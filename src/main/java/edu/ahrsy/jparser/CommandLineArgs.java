package edu.ahrsy.jparser;

public class CommandLineArgs {
  private String srcPath;
  private Integer complianceLevel;

  public CommandLineArgs() {}

  public String getSrcPath() {
    return srcPath;
  }

  public void setSrcPath(String srcPath) {
    this.srcPath = srcPath;
  }

  public Integer getComplianceLevel() {
    return complianceLevel;
  }

  public void setComplianceLevel(Integer complianceLevel) {
    this.complianceLevel = complianceLevel;
  }
}
