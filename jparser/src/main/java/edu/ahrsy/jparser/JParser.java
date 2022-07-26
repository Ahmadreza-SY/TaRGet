package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import edu.ahrsy.jparser.cli.CommandCallGraphs;
import edu.ahrsy.jparser.cli.CommandTestClasses;
import edu.ahrsy.jparser.cli.CommandTestMethods;
import edu.ahrsy.jparser.entity.TestClass;
import edu.ahrsy.jparser.entity.TestRepair;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.utils.FileUtils;

import java.io.File;
import java.nio.file.Path;
import java.util.HashSet;
import java.util.stream.Collectors;

public class JParser {
  private static final String TEST_CLASSES_CMD = "testClasses";
  private static final String TEST_METHODS_CMD = "testMethods";
  private static final String CALL_GRAPHS_CMD = "callGraphs";


  public static void cTestClasses(CommandTestClasses args) {
    Spoon.initializeSpoon(args);
    var srcURI = new File(args.srcPath).toURI();
    var ctTestClasses = Spoon.getAllTestClasses();
    var testClasses = ctTestClasses
            .stream()
            .map(ctClass -> {
              var absFile = ctClass.getPosition().getCompilationUnit().getFile();
              return new TestClass(ctClass.getQualifiedName(), srcURI.relativize(absFile.toURI()).getPath());
            })
            .collect(Collectors.toList());
    FileUtils.toCsv(testClasses, args.outputFile);
  }

  public static void cTestMethods(CommandTestMethods args) {
    Spoon.initializeSpoon(args);
    for (var method : Spoon.getTestMethods())
      FileUtils.saveFile(Path.of(args.outputPath, method.getSignature()), method.prettyprint());
  }

  public static void cCallGraphs(CommandCallGraphs args) {
    Spoon.initializeSpoon(args);
    var allRepairs = FileUtils.readCsv(
            Path.of(args.outputPath, "test_repair_info.csv").toString(),
            TestRepair.class
    );
    var releaseRepairs = allRepairs.stream().filter(r -> r.baseTag.equals(args.releaseTag))
            .collect(Collectors.toList());
    var repairedMethods = releaseRepairs.stream().map(TestRepair::getMethodSignature).collect(Collectors.toCollection(
            HashSet::new));
    var methods = Spoon.getMethodsByName(repairedMethods);
    for (var method : methods) {
      var callGraph = new CallGraph(method);
      callGraph.createCallGraph();
      callGraph.save(args.outputPath, args.releaseTag, args.srcPath);
    }
  }

  public static void main(String[] args) {
    CommandTestClasses testClassesArgs = new CommandTestClasses();
    CommandTestMethods testMethodsArgs = new CommandTestMethods();
    CommandCallGraphs callGraphsArgs = new CommandCallGraphs();
    JCommander jc = JCommander.newBuilder()
            .addCommand(TEST_CLASSES_CMD, testClassesArgs)
            .addCommand(TEST_METHODS_CMD, testMethodsArgs)
            .addCommand(CALL_GRAPHS_CMD, callGraphsArgs)
            .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case TEST_CLASSES_CMD:
        cTestClasses(testClassesArgs);
        break;
      case TEST_METHODS_CMD:
        cTestMethods(testMethodsArgs);
        break;
      case CALL_GRAPHS_CMD:
        cCallGraphs(callGraphsArgs);
    }
  }
}
