package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import edu.ahrsy.jparser.cli.*;
import edu.ahrsy.jparser.utils.IOUtils;

public class Application {
  private static final String COMPARE_CMD = "compare";
  private static final String COVERAGE_CMD = "coverage";

  public static void main(String[] args) {
    IOUtils.disableReflectionWarning();
    CommandCompare compareArgs = new CommandCompare();
    CommandCoverage coverageArgs = new CommandCoverage();
    JCommander jc = JCommander.newBuilder()
            .addCommand(COMPARE_CMD, compareArgs)
            .addCommand(COVERAGE_CMD, coverageArgs)
            .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case COMPARE_CMD:
        CommandCompare.cCompare(compareArgs);
        break;
      case COVERAGE_CMD:
        CommandCoverage.cCoverage(coverageArgs);
        break;
    }
  }
}
