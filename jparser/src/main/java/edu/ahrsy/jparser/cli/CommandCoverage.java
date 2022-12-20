package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.entity.TestChangeCoverage;
import edu.ahrsy.jparser.entity.TestRepair;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBar;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;
import spoon.reflect.declaration.CtMethod;

import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

public class CommandCoverage {
  @Parameter(names = {"-o", "--output-path"}, description = "The root output folder of the repo's collected data",
          required = true)
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;

  public static void cCoverage(CommandCoverage args) {
    var repairedTestsJSON = IOUtils.readFile(Path.of(args.outputPath, "repaired_tests.json"));
    var gson = IOUtils.createGsonInstance();
    List<SingleHunkTestChange> repairedTests = gson.fromJson(repairedTestsJSON,
            new TypeToken<ArrayList<SingleHunkTestChange>>() {
            }.getType());
    var repairedTestsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.bCommit));

    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .setInitialMax(repairedTests.size())
            .showSpeed()
            .setTaskName("Computing call graphs")
            .build();
    for (var entry : repairedTestsMap.entrySet()) {
      var bCommit = entry.getKey();
      var commitRepairs = entry.getValue();
      var srcPath = Path.of(args.outputPath, "commits", bCommit).toString();
      var spoon = new Spoon(srcPath, args.complianceLevel);
      var names = commitRepairs.stream().map(r -> r.name).collect(Collectors.toCollection(HashSet::new));
      var paths = commitRepairs.stream().map(r -> r.bPath).collect(Collectors.toCollection(HashSet::new));
      var methods = spoon.getExecutablesByName(names, paths, srcPath)
              .stream()
              .map(m -> (CtMethod<?>) m)
              .collect(Collectors.toList());
      for (var method : methods) {
        var callGraph = new CallGraph(method, spoon);
        callGraph.createCallGraph();
        var graphJSON = callGraph.toJSON(srcPath);
        var graphFile = Path.of(args.outputPath,
                "callGraphs",
                bCommit,
                method.getTopLevelType().getSimpleName(),
                method.getSimpleName(),
                Path.of(Spoon.getRelativePath(method, srcPath)).getParent().toString(),
                "graph.json");
        IOUtils.saveFile(graphFile, graphJSON);
        pb.step();
      }
    }
    pb.close();
  }
}
