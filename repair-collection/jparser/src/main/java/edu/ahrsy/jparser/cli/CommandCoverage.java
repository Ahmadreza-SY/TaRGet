package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.Gson;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.CommitDiffParser;
import edu.ahrsy.jparser.entity.CommitChangedClasses;
import edu.ahrsy.jparser.entity.CommitChanges;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.entity.TestElements;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.graph.dto.CallGraphDTO;
import edu.ahrsy.jparser.refactoringminer.RenameRefactoring;
import edu.ahrsy.jparser.refactoringminer.RefactoringMinerAPI;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.GitAPI;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;
import spoon.reflect.declaration.CtMethod;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.concurrent.*;
import java.util.stream.Collectors;
import java.util.stream.Stream;

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
    createCallGraphsAndElements(args, repairedTests);
    mineRefactorings(args, repairedTests);

    var changedSUTClassesJSON = IOUtils.readFile(Path.of(args.outputPath, "codeMining", "changed_sut_classes.json"));
    List<CommitChangedClasses> changedSUTClasses = gson.fromJson(changedSUTClassesJSON,
        new TypeToken<List<CommitChangedClasses>>() {
        }.getType());
    extractChanges(args, changedSUTClasses);
  }

  private static void createCallGraphsAndElements(CommandCoverage args, List<SingleHunkTestChange> repairedTests) {
    var callGraphsPath = Path.of(args.outputPath, "codeMining", "call_graphs.json");
    var testElementsPath = Path.of(args.outputPath, "codeMining", "test_elements.json");
    if (Files.exists(callGraphsPath) && Files.exists(testElementsPath)) {
      System.out.println("Call graphs and test elements exist, skipping ...");
      return;
    }

    var bCommitRepairsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.bCommit));
    var aCommitRepairsMap = repairedTests.stream().collect(Collectors.groupingBy(r -> r.aCommit));
    var allCommits = new HashSet<String>();
    allCommits.addAll(bCommitRepairsMap.keySet());
    allCommits.addAll(aCommitRepairsMap.keySet());

    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .setInitialMax(allCommits.size())
        .showSpeed()
        .setTaskName("Computing call graphs and test elements")
        .build();

    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);

    var callGraphs = Collections.synchronizedMap(new HashMap<String, Map<String, CallGraphDTO>>());
    var testElements = Collections.synchronizedMap(new HashMap<String, Map<String, TestElements>>());
    
    for (var commit : allCommits) {
      executor.submit(() -> {
        try {
          var repairs = new ArrayList<SingleHunkTestChange>();
          if (bCommitRepairsMap.containsKey(commit))
            repairs.addAll(bCommitRepairsMap.get(commit));
          if (aCommitRepairsMap.containsKey(commit))
            repairs.addAll(aCommitRepairsMap.get(commit));
          var testNames = repairs.stream().map(r -> r.name).collect(Collectors.toCollection(HashSet::new));
          var testPaths = repairs.stream().map(r -> r.bPath).collect(Collectors.toCollection(HashSet::new));
          var srcPath = GitAPI.createWorktree(repoDir, commit).toString();
          var spoon = new Spoon(srcPath, args.complianceLevel);
          var testMethods = spoon.getExecutablesByName(testNames, testPaths)
              .stream()
              .map(m -> (CtMethod<?>) m)
              .collect(Collectors.toList());
          for (var test : testMethods) {
            var callGraph = new CallGraph(test, spoon);
            callGraph.createCallGraph();
            if (!callGraphs.containsKey(commit))
              callGraphs.put(commit, Collections.synchronizedMap(new HashMap<>()));
            callGraphs.get(commit).put(Spoon.getUniqueName(test), callGraph.toDTO(srcPath));

            if (!testElements.containsKey(commit))
              testElements.put(commit, Collections.synchronizedMap(new HashMap<>()));
            testElements.get(commit).put(Spoon.getUniqueName(test), Spoon.getElements(test));
          }
          GitAPI.removeWorktree(repoDir, commit);
          pb.step();
        } catch (Exception e) {
          e.printStackTrace(System.out);
          pb.step();
        }
      });
    }

    awaitTerminationAfterShutdown(executor);
    pb.close();

    IOUtils.saveFile(callGraphsPath, gson.toJson(callGraphs));
    IOUtils.saveFile(testElementsPath, gson.toJson(testElements));
  }

  private static void mineRefactorings(CommandCoverage args, List<SingleHunkTestChange> repairedTests) {
    var refactoringsPath = Path.of(args.outputPath, "codeMining", "rename_refactorings.json");
    if (Files.exists(refactoringsPath)) {
      System.out.println("Refactorings already mined, skipping ...");
      return;
    }
    var renameRefactorings = Collections.synchronizedMap(new HashMap<String, List<RenameRefactoring>>());
    var aCommits = repairedTests.stream().map(r -> r.aCommit).distinct().collect(Collectors.toList());
    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .setInitialMax(aCommits.size())
        .showSpeed()
        .setTaskName("Mining refactorings")
        .build();
    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);
    for (String aCommit : aCommits) {
      executor.submit(() -> {
        var refactorings = RefactoringMinerAPI.mineRenameRefactorings(aCommit, repoDir.toString());
        renameRefactorings.put(aCommit, refactorings);
        pb.step();
      });
    }
    awaitTerminationAfterShutdown(executor);
    pb.close();

    IOUtils.saveFile(refactoringsPath, gson.toJson(renameRefactorings));
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
        try {
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
        } catch (Exception e) {
          e.printStackTrace();
        }
      });
    }

    awaitTerminationAfterShutdown(executor);
    pb.close();

    IOUtils.saveFile(SUTClassChangesPath, gson.toJson(SUTClassChanges));
    IOUtils.saveFile(SUTExecutableChangesPath, gson.toJson(SUTExecutableChanges));
  }
}
