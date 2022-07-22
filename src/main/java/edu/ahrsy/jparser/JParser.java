package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import edu.ahrsy.jparser.cli.Command;
import edu.ahrsy.jparser.cli.CommandTestClasses;
import edu.ahrsy.jparser.cli.CommandTestMethods;
import edu.ahrsy.jparser.entity.TestClass;
import edu.ahrsy.jparser.utils.FileUtils;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;

public class JParser {
  private static final String TEST_CLASSES_CMD = "testClasses";
  private static final String TEST_METHODS_CMD = "testMethods";
  private static SpoonAPI spoon;

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

  private static void initializeSpoon(Command cmd) {
    spoon = new Launcher();
    spoon.addInputResource(cmd.srcPath);
    if (cmd.complianceLevel != null)
      spoon.getEnvironment().setComplianceLevel(cmd.complianceLevel);
    spoon.buildModel();
  }

  public static void cTestClasses(CommandTestClasses args) {
    initializeSpoon(args);
    var srcURI = new File(args.srcPath).toURI();
    var ctTestClasses = getAllTestClasses();
    var testClasses = ctTestClasses
            .stream()
            .map(ctClass -> {
              var absFile = ctClass.getPosition().getCompilationUnit().getFile();
              return new TestClass(ctClass.getQualifiedName(), srcURI.relativize(absFile.toURI()).getPath());
            })
            .collect(Collectors.toList());
    FileUtils.toCsv(testClasses, args.outputFile);
  }

  public static void cTestMethods(CommandTestMethods args) {
    initializeSpoon(args);
    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    for (var type : spoon.getModel().getAllTypes()) {
      for (var method : type.getMethodsAnnotatedWith(juTestRef))
        FileUtils.saveFile(Path.of(args.outputPath, method.getSignature()), method.prettyprint());
    }
  }

  public static void main(String[] args) {
    CommandTestClasses testClassesArgs = new CommandTestClasses();
    CommandTestMethods testMethodsArgs = new CommandTestMethods();
    JCommander jc = JCommander.newBuilder()
            .addCommand(TEST_CLASSES_CMD, testClassesArgs)
            .addCommand(TEST_METHODS_CMD, testMethodsArgs)
            .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case TEST_CLASSES_CMD:
        cTestClasses(testClassesArgs);
        break;
      case TEST_METHODS_CMD:
        cTestMethods(testMethodsArgs);
        break;
    }
  }
}
