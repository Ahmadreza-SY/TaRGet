package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;

public class CommandMethodChanges {
  @Parameter(names = {"-o", "--output-path"},
          description = "The root output folder of the repo's collected data",
          required = true
  )
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;
}
