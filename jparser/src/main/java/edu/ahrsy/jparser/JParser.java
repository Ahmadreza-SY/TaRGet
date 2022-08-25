package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.cli.CommandCallGraphs;
import edu.ahrsy.jparser.cli.CommandMethodChanges;
import edu.ahrsy.jparser.cli.CommandTestClasses;
import edu.ahrsy.jparser.cli.CommandTestMethods;
import edu.ahrsy.jparser.entity.ReleaseMethodChanges;
import edu.ahrsy.jparser.entity.TestChangeCoverage;
import edu.ahrsy.jparser.entity.TestClass;
import edu.ahrsy.jparser.entity.TestRepair;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBar;
import spoon.reflect.declaration.CtMethod;

import java.io.File;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

public class JParser {
  private static final String TEST_CLASSES_CMD = "testClasses";
  private static final String TEST_METHODS_CMD = "testMethods";
  private static final String CALL_GRAPHS_CMD = "callGraphs";
  private static final String METHOD_CHANGES_CMD = "methodChanges";


  public static void cTestClasses(CommandTestClasses args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    var srcURI = new File(args.srcPath).toURI();
    var ctTestClasses = spoon.getAllTestClasses();
    var testClasses = ctTestClasses.stream().map(ctClass -> {
      var absFile = ctClass.getPosition().getCompilationUnit().getFile();
      return new TestClass(ctClass.getQualifiedName(), srcURI.relativize(absFile.toURI()).getPath());
    }).collect(Collectors.toList());
    IOUtils.toCsv(testClasses, args.outputFile);
  }

  public static void cTestMethods(CommandTestMethods args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    for (var method : spoon.getTestMethods())
      IOUtils.saveFile(Path.of(args.outputPath, method.getSignature()), Spoon.prettyPrintWithoutComments(method));
  }

  public static void cCallGraphs(CommandCallGraphs args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    var allRepairs = IOUtils.readCsv(Path.of(args.outputPath, "repairs", "test_repair_info.csv").toString(),
            TestRepair.class);
    var releaseRepairs = allRepairs.stream()
            .filter(r -> r.baseTag.equals(args.releaseTag))
            .collect(Collectors.toList());
    var repairedMethods = releaseRepairs.stream()
            .map(TestRepair::getMethodSignature)
            .collect(Collectors.toCollection(HashSet::new));
    var repairedMethodPaths = releaseRepairs.stream()
            .map(TestRepair::getPath)
            .collect(Collectors.toCollection(HashSet::new));
    var methods = spoon.getExecutablesByName(repairedMethods, repairedMethodPaths, args.srcPath);
    for (var method : methods) {
      var callGraph = new CallGraph(method, spoon);
      callGraph.createCallGraph();
      var relatedMethods = spoon.getTestPreAndPostMethods((CtMethod<?>) method);
      for (var relatedMethod : relatedMethods)
        callGraph.addSubGraph(relatedMethod);
      callGraph.save(args.outputPath, args.releaseTag, args.srcPath);
    }
  }

  public static void cMethodChanges(CommandMethodChanges args) {
    String changeCoverageJson = IOUtils.readFile(Path.of(args.outputPath, "repairs", "test_change_coverage.json"));
    var gson = IOUtils.createGsonInstance();
    List<TestChangeCoverage> testChangeCoverages = gson.fromJson(changeCoverageJson,
            new TypeToken<ArrayList<TestChangeCoverage>>() {
            }.getType());

    var releaseChangedFileMap = new HashMap<String, Set<String>>();
    for (var changeCoverage : testChangeCoverages) {
      String release = String.format("%s$%s", changeCoverage.baseTag, changeCoverage.headTag);
      if (!releaseChangedFileMap.containsKey(release)) releaseChangedFileMap.put(release, new HashSet<>());
      releaseChangedFileMap.get(release).addAll(changeCoverage.coveredChangedFiles);
    }

    var allReleasesMethodChanges = new ArrayList<ReleaseMethodChanges>();
    for (var entry : ProgressBar.wrap(releaseChangedFileMap.entrySet(), "Detecting methods changes")) {
      if (entry.getValue().isEmpty()) continue;
      var tags = entry.getKey().split("\\$");
      String baseSrcPath = Path.of(args.outputPath, "releases", tags[0], "code").toString();
      String headSrcPath = Path.of(args.outputPath, "releases", tags[1], "code").toString();

      var changedFiles = entry.getValue();
      var methodDiffParser = new MethodDiffParser(baseSrcPath, headSrcPath, args.complianceLevel);
      var methodChanges = methodDiffParser.detectMethodsChanges(changedFiles);
      allReleasesMethodChanges.add(new ReleaseMethodChanges(tags[0], tags[1], methodChanges));
    }

    var outputJson = gson.toJson(allReleasesMethodChanges);
    IOUtils.saveFile(Path.of(args.outputPath, "repairs", "test_coverage_changed_methods.json"), outputJson);
  }

  public static void main(String[] args) {
    IOUtils.disableReflectionWarning();
    CommandTestClasses testClassesArgs = new CommandTestClasses();
    CommandTestMethods testMethodsArgs = new CommandTestMethods();
    CommandCallGraphs callGraphsArgs = new CommandCallGraphs();
    CommandMethodChanges methodChangesArgs = new CommandMethodChanges();
    JCommander jc = JCommander.newBuilder()
            .addCommand(TEST_CLASSES_CMD, testClassesArgs)
            .addCommand(TEST_METHODS_CMD, testMethodsArgs)
            .addCommand(CALL_GRAPHS_CMD, callGraphsArgs)
            .addCommand(METHOD_CHANGES_CMD, methodChangesArgs)
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
        break;
      case METHOD_CHANGES_CMD:
        cMethodChanges(methodChangesArgs);
    }
  }
}
