package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.CommitDiffParser;
import edu.ahrsy.jparser.entity.CommitChangedClasses;
import edu.ahrsy.jparser.entity.CommitChanges;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.refactoringminer.RefactoringInfo;
import edu.ahrsy.jparser.refactoringminer.RefactoringMinerAPI;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.GitAPI;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBar;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;
import org.apache.commons.lang3.tuple.ImmutablePair;
import spoon.reflect.declaration.CtMethod;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;

import static edu.ahrsy.jparser.utils.IOUtils.awaitTerminationAfterShutdown;

public class CommandCoverage {
  @Parameter(names = {"-o", "--output-path"}, description = "The root output folder of the repo's collected data",
      required = true)
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;

  private static final Gson gson = IOUtils.createGsonInstance();
  private static Path repoDir = null;

  public static void cCoverage(CommandCoverage args) {
    repoDir = Path.of(args.outputPath, "codeMining", "clone");
    GitAPI.cleanupWorktrees(repoDir);

    var repairedTestsJSON = IOUtils.readFile(Path.of(args.outputPath, "codeMining", "repaired_tests.json"));
    List<SingleHunkTestChange> repairedTests = gson.fromJson(repairedTestsJSON,
        new TypeToken<ArrayList<SingleHunkTestChange>>() {
        }.getType());
    createCallGraphs(args, repairedTests);
    mineRefactorings(args, repairedTests);

    var changedSUTClassesJSON = IOUtils.readFile(Path.of(args.outputPath, "codeMining", "changed_sut_classes.json"));
    List<CommitChangedClasses> changedSUTClasses = gson.fromJson(changedSUTClassesJSON,
        new TypeToken<List<CommitChangedClasses>>() {
        }.getType());
    extractChanges(args, changedSUTClasses);
  }

  private static Integer countNumberOfGraphFiles(Path graphsPath) {
    try {
      try (var files = Files.find(graphsPath,
          Integer.MAX_VALUE,
          (path, bfa) -> path.toString().endsWith("graph.json"))) {
        return (int) files.count();
      }
    } catch (IOException e) {
      return 0;
    }
  }

  private static void createCallGraphs(CommandCoverage args, List<SingleHunkTestChange> repairedTests) {
    var aCommitRepairsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.aCommit));
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .setInitialMax(repairedTests.size())
        .showSpeed()
        .setTaskName("Computing call graphs")
        .build();

    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);

    for (var aEntry : aCommitRepairsMap.entrySet()) {
      executor.submit(() -> {
        var aCommit = aEntry.getKey();
        var aCommitRepairs = aEntry.getValue();
        var commitGraphsPath = Path.of(args.outputPath, "codeMining", "callGraphs", aCommit);
        if (countNumberOfGraphFiles(commitGraphsPath) == aCommitRepairs.size()) {
          pb.stepBy(aCommitRepairs.size());
          return;
        }
        // Each aCommit can only have exactly one bCommit
        var bCommit = aCommitRepairs.get(0).bCommit;
        var names = aCommitRepairs.stream().map(r -> r.name).collect(Collectors.toCollection(HashSet::new));
        var paths = aCommitRepairs.stream().map(r -> r.bPath).collect(Collectors.toCollection(HashSet::new));
        var srcPath = GitAPI.createWorktree(repoDir, bCommit).toString();
        var spoon = new Spoon(srcPath, args.complianceLevel);
        var executables = spoon.getExecutablesByName(names, paths)
            .stream()
            .map(m -> (CtMethod<?>) m)
            .collect(Collectors.toList());
        for (var executable : executables) {
          var callGraph = new CallGraph(executable, spoon);
          callGraph.createCallGraph();
          var graphJSON = callGraph.toJSON(srcPath);
          var graphFile = Path.of(commitGraphsPath.toString(),
              executable.getTopLevelType().getSimpleName(),
              executable.getSimpleName(),
              Path.of(Spoon.getRelativePath(executable, srcPath)).getParent().toString(),
              "graph.json");
          IOUtils.saveFile(graphFile, graphJSON);
          pb.step();
        }
        GitAPI.removeWorktree(repoDir, bCommit);
      });
    }

    awaitTerminationAfterShutdown(executor);
    pb.close();
  }

  private static void mineRefactorings(CommandCoverage args, List<SingleHunkTestChange> repairedTests) {
    var refactoringsPath = Path.of(args.outputPath, "codeMining", "refactorings.json");
    var projectPath = Path.of(args.outputPath, "codeMining", "clone").toString();
    if (Files.exists(refactoringsPath)) {
      System.out.println("Refactorings already mined, skipping ...");
      return;
    }
    var commitRefactorings = new HashMap<String, List<RefactoringInfo>>();
    var aCommits = repairedTests.stream().map(r -> r.aCommit).distinct().collect(Collectors.toList());
    var pbb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .showSpeed()
        .setTaskName("Mining refactorings");
    for (String aCommit : ProgressBar.wrap(aCommits, pbb)) {
      var refactorings = RefactoringMinerAPI.mineCommitRefactorings(aCommit, projectPath);
      commitRefactorings.put(aCommit, refactorings);
    }

    IOUtils.saveFile(refactoringsPath, gson.toJson(commitRefactorings));
  }

  private static void extractChanges(CommandCoverage args, List<CommitChangedClasses> changedSUTClasses) {
    var SUTClassChangesPath = Path.of(args.outputPath, "codeMining", "sut_class_changes.json");
    var SUTExecutableChangesPath = Path.of(args.outputPath, "codeMining", "sut_method_changes.json");
    if (Files.exists(SUTClassChangesPath) && Files.exists(SUTExecutableChangesPath)) {
      System.out.println("SUT class and method changes already exist, skipping ...");
      return;
    }

    var SUTClassChanges = Collections.synchronizedList(new ArrayList<CommitChanges>());
    var SUTExecutableChanges = Collections.synchronizedList(new ArrayList<CommitChanges>());
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .setInitialMax(changedSUTClasses.stream().mapToInt(c -> c.changedClasses.size()).sum())
        .showSpeed()
        .setTaskName("Extracting SUT changes")
        .build();
    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);

    for (var changedClasses : changedSUTClasses) {
      executor.submit(() -> {
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
      });
    }

    awaitTerminationAfterShutdown(executor);
    pb.close();

    IOUtils.saveFile(SUTClassChangesPath, gson.toJson(SUTClassChanges));
    IOUtils.saveFile(SUTExecutableChangesPath, gson.toJson(SUTExecutableChanges));
  }
}
