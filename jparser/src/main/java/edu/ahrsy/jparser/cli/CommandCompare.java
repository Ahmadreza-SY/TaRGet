package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import edu.ahrsy.jparser.entity.ChangedTestClass;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.TestClassComparator;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBar;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.stream.Collectors;

public class CommandCompare {
  @Parameter(names = {"-o", "--output-path"}, description = "Output folder for saving refactorings", required = true)
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;

  public static void cCompare(CommandCompare args) {
    var changedTestsPath = Path.of(args.outputPath, "changed_tests.json");
    if (Files.exists(changedTestsPath)) {
      System.out.println("Changed tests already exists, skipping ...");
      return;
    }
    var allChanges = IOUtils.readCsv(Path.of(args.outputPath, "changed_test_classes.csv").toString(),
            ChangedTestClass.class);
    var allSingleHunkTestChanges = new ArrayList<SingleHunkTestChange>();
    var pbb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
            .showSpeed()
            .setTaskName("Extracting test method changes");
    for (ChangedTestClass changedTestClass : ProgressBar.wrap(allChanges, pbb)) {
      var bPath = Path.of(args.outputPath, "testClasses", changedTestClass.beforeCommit, changedTestClass.beforePath);
      var aPath = Path.of(args.outputPath, "testClasses", changedTestClass.afterCommit, changedTestClass.afterPath);
      var classComparator = new TestClassComparator(bPath.toString(), aPath.toString(), args.complianceLevel);
      var testChanges = classComparator.getSingleHunkMethodChanges(changedTestClass, args.outputPath)
              .stream()
              .map(mc -> new SingleHunkTestChange(mc.getName(),
                      classComparator.getBeforeTestSource(mc.getName()),
                      changedTestClass.beforePath,
                      changedTestClass.afterPath,
                      changedTestClass.beforeCommit,
                      changedTestClass.afterCommit,
                      mc.getHunks().get(0)))
              .collect(Collectors.toList());
      allSingleHunkTestChanges.addAll(testChanges);
    }
    var gson = IOUtils.createGsonInstance();
    var outputJson = gson.toJson(allSingleHunkTestChanges);
    IOUtils.saveFile(changedTestsPath, outputJson);
    System.out.printf("Found %d single-hunk changed tests%n", allSingleHunkTestChanges.size());
  }
}
