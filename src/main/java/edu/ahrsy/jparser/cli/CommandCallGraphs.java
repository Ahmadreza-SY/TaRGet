package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;

public class CommandCallGraphs extends Command {
  @Parameter(names = {"-o", "--output-path"}, description = "The root output folder of the repo's collected data", required = true)
  public String outputPath;

  @Parameter(names = {"-t", "--release-tag"}, description = "The release tag of the repo for call graph extraction", required = true)
  public String releaseTag;
}
