package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import edu.ahrsy.jparser.cli.*;
import edu.ahrsy.jparser.utils.IOUtils;

public class JParser {
  private static final String TEST_CLASSES_CMD = "testClasses";
  private static final String TEST_METHODS_CMD = "testMethods";
  private static final String CALL_GRAPHS_CMD = "callGraphs";
  private static final String METHOD_CHANGES_CMD = "methodChanges";
  private static final String REFACTORINGS_CMD = "refactorings";
  private static final String COMPARE_CMD = "compare";

  public static void main(String[] args) {
    IOUtils.disableReflectionWarning();
    CommandTestClasses testClassesArgs = new CommandTestClasses();
    CommandTestMethods testMethodsArgs = new CommandTestMethods();
    CommandCallGraphs callGraphsArgs = new CommandCallGraphs();
    CommandMethodChanges methodChangesArgs = new CommandMethodChanges();
    CommandRefactoring refactoringArgs = new CommandRefactoring();
    CommandCompare compareArgs = new CommandCompare();
    JCommander jc = JCommander.newBuilder()
            .addCommand(TEST_CLASSES_CMD, testClassesArgs)
            .addCommand(TEST_METHODS_CMD, testMethodsArgs)
            .addCommand(CALL_GRAPHS_CMD, callGraphsArgs)
            .addCommand(METHOD_CHANGES_CMD, methodChangesArgs)
            .addCommand(REFACTORINGS_CMD, refactoringArgs)
            .addCommand(COMPARE_CMD, compareArgs)
            .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case TEST_CLASSES_CMD:
        CommandTestClasses.cTestClasses(testClassesArgs);
        break;
      case TEST_METHODS_CMD:
        CommandTestMethods.cTestMethods(testMethodsArgs);
        break;
      case CALL_GRAPHS_CMD:
        CommandCallGraphs.cCallGraphs(callGraphsArgs);
        break;
      case METHOD_CHANGES_CMD:
        CommandMethodChanges.cMethodChanges(methodChangesArgs);
        break;
      case REFACTORINGS_CMD:
        CommandRefactoring.cRefactoring(refactoringArgs);
        break;
      case COMPARE_CMD:
        CommandCompare.cCompare(compareArgs);
        break;
    }
  }
}
