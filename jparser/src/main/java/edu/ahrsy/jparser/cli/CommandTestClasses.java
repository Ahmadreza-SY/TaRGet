package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import edu.ahrsy.jparser.entity.TestClass;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;

import java.io.File;
import java.util.stream.Collectors;

public class CommandTestClasses extends Command {
  @Parameter(names = {"-o", "--output-file"}, description = "Output file for saving the results", required = true)
  public String outputFile;

  public static void cTestClasses(CommandTestClasses args) {
    var spoon = new Spoon(args.srcPath, args.complianceLevel);
    var srcURI = new File(args.srcPath).toURI();
    var ctTestClasses = spoon.getAllTestClasses();
    var testClasses = ctTestClasses.stream().map(ctClass -> {
      var absFile = ctClass.getPosition().getCompilationUnit().getFile();
      return new TestClass(ctClass.getQualifiedName(), srcURI.relativize(absFile.toURI()).getPath());
    }).collect(Collectors.toList());
    IOUtils.toCsv(testClasses, args.outputFile);
  }
}
