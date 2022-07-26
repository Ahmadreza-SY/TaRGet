package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;

public class CommandTestMethods extends Command {
  @Parameter(names = {"-o", "--output-path"},
          description = "Output folder for saving method source code",
          required = true
  )
  public String outputPath;
}
