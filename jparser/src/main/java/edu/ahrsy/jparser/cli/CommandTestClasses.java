package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;

public class CommandTestClasses extends Command {
  @Parameter(names = {"-o", "--output-file"}, description = "Output file for saving the results", required = true)
  public String outputFile;
}
