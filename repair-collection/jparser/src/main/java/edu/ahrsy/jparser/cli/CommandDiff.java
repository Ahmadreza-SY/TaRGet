package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.Gson;
import edu.ahrsy.jparser.gumtree.GumTreeUtils;
import edu.ahrsy.jparser.gumtree.RepairPatch;
import edu.ahrsy.jparser.gumtree.RepairType;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBarBuilder;
import me.tongfei.progressbar.ProgressBarStyle;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.concurrent.Executors;

import static edu.ahrsy.jparser.utils.IOUtils.awaitTerminationAfterShutdown;

public class CommandDiff {
  @Parameter(names = {"-o", "--output-path"}, description = "Output folder for saving refactorings", required = true)
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 11;

  public static void cDiff(CommandDiff args) {
    var repairPatches = IOUtils.readCsv(Path.of(args.outputPath, "repair_patches.csv").toString(),
        RepairPatch.class);

    var pb = new ProgressBarBuilder().setStyle(ProgressBarStyle.ASCII)
        .setInitialMax(repairPatches.size())
        .showSpeed()
        .setTaskName("Categorizing repair patches")
        .build();
    int procCnt = Runtime.getRuntime().availableProcessors();
    var executor = Executors.newFixedThreadPool(procCnt);
    var repairTypes = Collections.synchronizedList(new ArrayList<RepairType>());
    for (RepairPatch repairPatch : repairPatches) {
      executor.submit(() -> {
        repairPatch.beforePath = Path.of(args.outputPath, repairPatch.beforePath).toString();
        repairPatch.afterPath = Path.of(args.outputPath, repairPatch.afterPath).toString();
        var repairType = GumTreeUtils.getRepairType(repairPatch, args.complianceLevel);
        repairTypes.add(repairType);
        pb.step();
      });
    }
    awaitTerminationAfterShutdown(executor);
    pb.close();

    Gson gson = IOUtils.createGsonInstance();
    IOUtils.saveFile(Path.of(args.outputPath, "repair_types.json"), gson.toJson(repairTypes));
    System.out.printf("Found total %d repair types.%n", repairTypes.size());
  }
}
