package edu.ahrsy.jparser;

import com.beust.jcommander.JCommander;
import com.opencsv.bean.StatefulBeanToCsv;
import com.opencsv.bean.StatefulBeanToCsvBuilder;
import com.opencsv.exceptions.CsvDataTypeMismatchException;
import com.opencsv.exceptions.CsvRequiredFieldEmptyException;
import edu.ahrsy.jparser.cli.Command;
import edu.ahrsy.jparser.cli.CommandTestClasses;
import edu.ahrsy.jparser.entity.TestClass;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.io.Writer;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.stream.Collectors;

public class JParser {
  private static final String TEST_CLASSES_CMD = "testClasses";
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
    try (Writer writer = new FileWriter(args.outputFile)) {
      StatefulBeanToCsv<TestClass> beanToCsv = new StatefulBeanToCsvBuilder<TestClass>(writer).build();
      beanToCsv.write(testClasses);
    } catch (IOException | CsvRequiredFieldEmptyException | CsvDataTypeMismatchException e) {
      throw new RuntimeException(e);
    }
  }

  public static void main(String[] args) {
    CommandTestClasses cTestClasses = new CommandTestClasses();
    JCommander jc = JCommander.newBuilder()
            .addCommand(TEST_CLASSES_CMD, cTestClasses)
            .build();
    jc.parse(args);

    switch (jc.getParsedCommand()) {
      case TEST_CLASSES_CMD:
        cTestClasses(cTestClasses);
        break;
    }

    /*CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    for (var testClass : getAllTestClasses()) {
      for (var method : testClass.getMethodsAnnotatedWith(juTestRef)) {
        CallGraph callGraph = new CallGraph();
        callGraph.createCallGraph(method);
      }
    }*/
  }
}
