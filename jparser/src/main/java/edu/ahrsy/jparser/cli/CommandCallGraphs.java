package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import edu.ahrsy.jparser.entity.TestRepair;
import edu.ahrsy.jparser.graph.CallGraph;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import spoon.reflect.declaration.CtMethod;

import java.nio.file.Path;
import java.util.HashSet;
import java.util.stream.Collectors;

public class CommandCallGraphs extends Command {
  @Parameter(names = {"-o", "--output-path"},
          description = "The root output folder of the repo's collected data",
          required = true
  )
  public String outputPath;

  @Parameter(names = {"-t", "--tag"},
          description = "The tag of the repo for call graph extraction",
          required = true
  )
  public String tag;

  public static void cCallGraphs(CommandCallGraphs args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    var allRepairs = IOUtils.readCsv(Path.of(args.outputPath, "repairs", "repaired_test_methods.csv").toString(),
            TestRepair.class);
    var tagRepairs = allRepairs.stream()
            .filter(r -> r.baseTag.equals(args.tag))
            .collect(Collectors.toList());
    var repairedMethods = tagRepairs.stream()
            .map(TestRepair::getMethodSignature)
            .collect(Collectors.toCollection(HashSet::new));
    var repairedMethodPaths = tagRepairs.stream()
            .map(TestRepair::getPath)
            .collect(Collectors.toCollection(HashSet::new));
    var methods = spoon.getExecutablesByName(repairedMethods, repairedMethodPaths, args.srcPath);
    for (var method : methods) {
      var callGraph = new CallGraph(method, spoon);
      callGraph.createCallGraph();
      var relatedMethods = spoon.getTestPreAndPostMethods((CtMethod<?>) method);
      for (var relatedMethod : relatedMethods)
        callGraph.addSubGraph(relatedMethod);
      callGraph.save(args.outputPath, args.tag, args.srcPath);
    }
  }
}
