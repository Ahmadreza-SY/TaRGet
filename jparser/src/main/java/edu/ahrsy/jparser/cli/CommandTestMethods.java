package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;

import java.nio.file.Path;

public class CommandTestMethods extends Command {
  @Parameter(names = {"-o", "--output-path"},
          description = "Output folder for saving method source code",
          required = true
  )
  public String outputPath;

  public static void cTestMethods(CommandTestMethods args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    for (var method : spoon.getTestMethods()) {
      String signature = Spoon.getSimpleSignature(method);
      IOUtils.saveFile(Path.of(args.outputPath, signature), Spoon.prettyPrint(method));
      String methodBody = Spoon.prettyPrint(method.getBody());
      IOUtils.saveFile(Path.of(args.outputPath).getParent().resolve("methodBodies").resolve(signature),
              methodBody == null ? signature : methodBody);
    }
  }
}
