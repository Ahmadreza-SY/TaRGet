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
import org.apache.commons.lang3.tuple.ImmutablePair;
import spoon.reflect.declaration.CtMethod;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
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
    var repoDir = Path.of(args.outputPath, "clone");
    var aCommitRepairsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.aCommit));
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .setInitialMax(repairedTests.size())
            .showSpeed()
            .setTaskName("Computing call graphs")
            .build();

    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);
    var latch = new CountDownLatch(aCommitRepairsMap.size());

    for (var aEntry : aCommitRepairsMap.entrySet()) {
      // WARN: rare race condition -> same bCommit for two aCommits
      // when one aCommit is analyzing code and second aCommit removes code
      executor.submit(() -> {
        var aCommit = aEntry.getKey();
        var aCommitRepairs = aEntry.getValue();
        var commitGraphsPath = Path.of(args.outputPath, "callGraphs", aCommit);
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
    try {
      latch.await();
    } catch (InterruptedException e) {
      throw new RuntimeException(e);
    }
    pb.close();
  }

  private static void extractChanges(CommandCoverage args, List<CommitChangedClasses> changedSUTClasses) {
    var SUTClassChangesPath = Path.of(args.outputPath, "sut_class_changes.json");
    var SUTExecutableChangesPath = Path.of(args.outputPath, "sut_method_changes.json");
    if (Files.exists(SUTClassChangesPath) && Files.exists(SUTExecutableChangesPath)) {
      System.out.println("SUT class and method changes already exist, skipping ...");
      return;
    }

    var repoDir = Path.of(args.outputPath, "clone");
    var SUTClassChanges = new ArrayList<CommitChanges>();
    var SUTExecutableChanges = new ArrayList<CommitChanges>();
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .setInitialMax(changedSUTClasses.stream().mapToInt(c -> c.changedClasses.size()).sum())
            .showSpeed()
            .setTaskName("Extracting SUT changes")
            .build();
    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);
    var latch = new CountDownLatch(changedSUTClasses.size());
    List<Future<ImmutablePair<CommitChanges, CommitChanges>>> futures = new ArrayList<>();

    for (var changedClasses : changedSUTClasses) {
      // WARN: rare race condition -> same bCommit for two aCommits
      // when one aCommit is analyzing code and second aCommit removes code
      Future<ImmutablePair<CommitChanges, CommitChanges>> future = executor.submit(() -> {
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
        GitAPI.removeWorktree(repoDir, changedClasses.bCommit);
        GitAPI.removeWorktree(repoDir, changedClasses.aCommit);
        return new ImmutablePair<>(commitClassChanges, commitExecutableChanges);
      });
      futures.add(future);
    }
    try {
      latch.await();
      for (var future : futures) {
        var result = future.get();
        SUTClassChanges.add(result.getLeft());
        SUTExecutableChanges.add(result.getRight());
      }
    } catch (InterruptedException | ExecutionException e) {
      throw new RuntimeException(e);
    }
    executor.shutdown();
    pb.close();

    IOUtils.saveFile(SUTClassChangesPath, gson.toJson(SUTClassChanges));
    IOUtils.saveFile(SUTExecutableChangesPath, gson.toJson(SUTExecutableChanges));
  }
}
