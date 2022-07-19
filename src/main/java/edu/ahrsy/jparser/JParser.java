package edu.ahrsy.jparser;

import org.apache.commons.cli.*;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

public class JParser {
  private static SpoonAPI spoon;

  private static void saveFile(Path filePath, String content) {
    try {
      Files.createDirectories(filePath.getParent());
      Files.write(filePath, content.getBytes());
    } catch (IOException e) {
      throw new RuntimeException(e);
    }
  }

  private static List<CtClass<?>> getAllTestClasses() {
    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    TypeFilter<CtClass<?>> isRealTestingClass =
            new TypeFilter<>(CtClass.class) {
              @Override
              public boolean matches(CtClass<?> ctClass) {
                // First step is to reuse standard filtering
                if (!super.matches(ctClass)) {
                  return false;
                }
                CtTypeReference<?> current = ctClass.getReference();
                // Walk up the chain of inheritance and find whether there is a method annotated as test
                do {
                  if (current.getDeclaration() != null &&
                          !current.getDeclaration().getMethodsAnnotatedWith(juTestRef).isEmpty()) {
                    return true;
                  }
                } while ((current = current.getSuperclass()) != null);
                return false;
              }
            };
    return spoon.getModel().getRootPackage().getElements(isRealTestingClass);
  }

  private static CommandLineArgs parseArgs(String[] args) {
    Options options = new Options();

    Option srcPath = new Option("p", "src-path", true, "Root path of the software system");
    srcPath.setRequired(true);
    options.addOption(srcPath);

    Option complianceLevel = new Option("cl", "compliance-level", true, "Java version compliance level");
    complianceLevel.setRequired(false);
    complianceLevel.setType(Number.class);
    options.addOption(complianceLevel);

    CommandLineParser parser = new DefaultParser();
    try {
      CommandLine cmd = parser.parse(options, args);
      CommandLineArgs cmdArgs = new CommandLineArgs();
      cmdArgs.setSrcPath(cmd.getOptionValue(srcPath));
      if (cmd.hasOption(complianceLevel))
        cmdArgs.setComplianceLevel(((Number) cmd.getParsedOptionValue(complianceLevel)).intValue());

      return cmdArgs;
    } catch (ParseException e) {
      System.out.println(e.getMessage());
      System.exit(1);
    }

    return new CommandLineArgs();
  }

  public static void main(String[] args) {
    CommandLineArgs cmdArgs = parseArgs(args);
    spoon = new Launcher();
    spoon.addInputResource(cmdArgs.getSrcPath());
    if (cmdArgs.getComplianceLevel() != null)
      spoon.getEnvironment().setComplianceLevel(cmdArgs.getComplianceLevel());
    spoon.buildModel();

    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    for (var testClass : getAllTestClasses()) {
      for (var method : testClass.getMethodsAnnotatedWith(juTestRef)) {
        CallGraph callGraph = new CallGraph();
        callGraph.createCallGraph(method);
      }
    }
  }
}
