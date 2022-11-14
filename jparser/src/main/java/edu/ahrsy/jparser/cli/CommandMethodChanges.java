package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.MethodDiffParser;
import edu.ahrsy.jparser.entity.*;
import edu.ahrsy.jparser.utils.IOUtils;
import me.tongfei.progressbar.ProgressBar;

import java.nio.file.Path;
import java.util.*;

public class CommandMethodChanges {
  @Parameter(names = {"-o", "--output-path"},
          description = "The root output folder of the repo's collected data",
          required = true
  )
  public String outputPath;

  @Parameter(names = {"-cl", "--compliance-level"}, description = "Java version compliance level")
  public Integer complianceLevel = 10;

  private static void extractTestMethodChanges(String outputPath) {
    var repairs = IOUtils.readCsv(Path.of(outputPath, "repairs", "test_repair_info.csv").toString(), TestRepair.class);
    var testChanges = new ArrayList<TestChange>();
    for (var repair : repairs) {
      var beforeRepair = IOUtils.readFile(Path.of(outputPath,
              "releases",
              repair.baseTag,
              "changed_tests",
              repair._class,
              "methodBodies",
              repair.method));
      var afterRepair = IOUtils.readFile(Path.of(outputPath,
              "releases",
              repair.headTag,
              "changed_tests",
              repair._class,
              "methodBodies",
              repair.method));

      var methodChange = new MethodChange(repair.path, repair.method);
      methodChange.extractHunks(beforeRepair, afterRepair);
      testChanges.add(new TestChange(repair._class + "." + repair.method,
              repair.baseTag,
              repair.headTag,
              methodChange.getHunks()));
    }

    var gson = IOUtils.createGsonInstance();
    var outputJson = gson.toJson(testChanges);
    IOUtils.saveFile(Path.of(outputPath, "repairs", "test_repair_changes.json"), outputJson);
  }

  public static void cMethodChanges(CommandMethodChanges args) {
    extractTestMethodChanges(args.outputPath);

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
}
