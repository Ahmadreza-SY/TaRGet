package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.CommitDiffParser;
import edu.ahrsy.jparser.entity.CommitChangedClasses;
import edu.ahrsy.jparser.entity.CommitChanges;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.GitAPI;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;
import spoon.reflect.declaration.CtMethod;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.stream.Collectors;

public class CommandCoverage {
  @Parameter(names = {"-o", "--output-path"}, description = "The root output folder of the repo's collected data",
          required = true)
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;

  private static final Gson gson = IOUtils.createGsonInstance();

  public static void cCoverage(CommandCoverage args) {
    var repoDir = Path.of(args.outputPath, "clone");
    GitAPI.cleanupWorktrees(repoDir);

    var repairedTestsJSON = IOUtils.readFile(Path.of(args.outputPath, "repaired_tests.json"));
    List<SingleHunkTestChange> repairedTests = gson.fromJson(repairedTestsJSON,
            new TypeToken<ArrayList<SingleHunkTestChange>>() {
            }.getType());
    createCallGraphs(args, repairedTests);

    var changedSUTClassesJSON = IOUtils.readFile(Path.of(args.outputPath, "changed_sut_classes.json"));
    List<CommitChangedClasses> changedSUTClasses = gson.fromJson(changedSUTClassesJSON,
            new TypeToken<List<CommitChangedClasses>>() {
            }.getType());
    extractChanges(args, changedSUTClasses);
  }

  private static void createCallGraphs(CommandCoverage args, List<SingleHunkTestChange> repairedTests) {
    var repoDir = Path.of(args.outputPath, "clone");
    var repairedTestsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.bCommit));
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .setInitialMax(repairedTests.size())
            .showSpeed()
            .setTaskName("Computing call graphs")
            .build();
    for (var entry : repairedTestsMap.entrySet()) {
      var bCommit = entry.getKey();
      var commitRepairs = entry.getValue();
      var srcPath = GitAPI.createWorktree(repoDir, bCommit).toString();
      var spoon = new Spoon(srcPath, args.complianceLevel);
      var names = commitRepairs.stream().map(r -> r.name).collect(Collectors.toCollection(HashSet::new));
      var paths = commitRepairs.stream().map(r -> r.bPath).collect(Collectors.toCollection(HashSet::new));
      var executables = spoon.getExecutablesByName(names, paths)
              .stream()
              .map(m -> (CtMethod<?>) m)
              .collect(Collectors.toList());
      for (var executable : executables) {
        var callGraph = new CallGraph(executable, spoon);
        callGraph.createCallGraph();
        var graphJSON = callGraph.toJSON(srcPath);
        var graphFile = Path.of(args.outputPath,
                "callGraphs",
                bCommit,
                executable.getTopLevelType().getSimpleName(),
                executable.getSimpleName(),
                Path.of(Spoon.getRelativePath(executable, srcPath)).getParent().toString(),
                "graph.json");
        IOUtils.saveFile(graphFile, graphJSON);
        pb.step();
      }
      GitAPI.removeWorktree(repoDir, bCommit);
    }
    pb.close();
  }

  private static void extractChanges(CommandCoverage args, List<CommitChangedClasses> changedSUTClasses) {
    var repoDir = Path.of(args.outputPath, "clone");
    var SUTClassChanges = new ArrayList<CommitChanges>();
    var SUTExecutableChanges = new ArrayList<CommitChanges>();
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .setInitialMax(changedSUTClasses.stream().mapToInt(c -> c.changedClasses.size()).sum())
            .showSpeed()
            .setTaskName("Extracting SUT changes")
            .build();
    for (var changedClasses : changedSUTClasses) {
      var bSrcPath = GitAPI.createWorktree(repoDir, changedClasses.bCommit).toString();
      var aSrcPath = GitAPI.createWorktree(repoDir, changedClasses.aCommit).toString();
      var parser = new CommitDiffParser(new Spoon(bSrcPath, args.complianceLevel),
              new Spoon(aSrcPath, args.complianceLevel));
      var commitClassChanges = new CommitChanges(changedClasses.bCommit, changedClasses.aCommit);
      var commitExecutableChanges = new CommitChanges(changedClasses.bCommit, changedClasses.aCommit);
      for (var changedClass : changedClasses.changedClasses) {
        var classChanges = parser.detectClassChanges(changedClass);
        if (classChanges != null) commitClassChanges.addChanges(Collections.singletonList(classChanges));
        commitExecutableChanges.addChanges(parser.detectExecutablesChanges(changedClass));
        pb.step();
      }
      SUTClassChanges.add(commitClassChanges);
      SUTExecutableChanges.add(commitExecutableChanges);
      GitAPI.removeWorktree(repoDir, changedClasses.bCommit);
      GitAPI.removeWorktree(repoDir, changedClasses.aCommit);
    }
    pb.close();
    IOUtils.saveFile(Path.of(args.outputPath, "sut_class_changes.json"), gson.toJson(SUTClassChanges));
    IOUtils.saveFile(Path.of(args.outputPath, "sut_method_changes.json"), gson.toJson(SUTExecutableChanges));
  }
}
