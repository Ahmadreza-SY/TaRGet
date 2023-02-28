package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import edu.ahrsy.jparser.cli.*;
import edu.ahrsy.jparser.utils.IOUtils;

public class Main {
  private static final String COMPARE_CMD = "compare";
  private static final String COVERAGE_CMD = "coverage";
  private static final String DIFF_CMD = "diff";

  public static void main(String[] args) {
    IOUtils.disableReflectionWarning();
    CommandCompare compareArgs = new CommandCompare();
    CommandCoverage coverageArgs = new CommandCoverage();
    CommandDiff diffArgs = new CommandDiff();
    JCommander jc = JCommander.newBuilder()
        .addCommand(COMPARE_CMD, compareArgs)
        .addCommand(COVERAGE_CMD, coverageArgs)
        .addCommand(DIFF_CMD, diffArgs)
        .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case COMPARE_CMD:
        CommandCompare.cCompare(compareArgs);
        break;
      case COVERAGE_CMD:
        CommandCoverage.cCoverage(coverageArgs);
        break;
      case DIFF_CMD:
        CommandDiff.cDiff(diffArgs);
        break;
    }
  }
}
