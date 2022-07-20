package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;

public class Command {
  @Parameter(names = {"-p", "--project-path"}, description = "Root path of the software system", required = true)
  public String srcPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel;
}
