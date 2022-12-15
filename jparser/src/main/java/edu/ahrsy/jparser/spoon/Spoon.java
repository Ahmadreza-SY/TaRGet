package edu.ahrsy.jparser.spoon;

import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.processing.Processor;
import spoon.reflect.code.CtBlock;
import spoon.reflect.cu.position.NoSourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.DefaultImportComparator;
import spoon.reflect.visitor.ForceImportProcessor;
import spoon.reflect.visitor.ImportCleaner;
import spoon.reflect.visitor.ImportConflictDetector;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Stream;

public class Spoon {
  private final SpoonAPI spoon;
  public String srcPath;

  public Spoon(String srcPath, Integer complianceLevel) {
    this.srcPath = srcPath;
    spoon = new Launcher();
    spoon.addInputResource(srcPath);
    spoon.getEnvironment().setIgnoreDuplicateDeclarations(true);
    if (complianceLevel != null) spoon.getEnvironment().setComplianceLevel(complianceLevel);
    spoon.getEnvironment().setCommentEnabled(false);
    spoon.getFactory().getEnvironment().setPrettyPrinterCreator(() -> {
      var printer = new CustomJavaPrettyPrinter(spoon.getFactory().getEnvironment());
      List<Processor<CtElement>> preprocessors = List.of(new ForceImportProcessor(),
              new ImportCleaner().setCanAddImports(false),
              new ImportConflictDetector(),
              new ImportCleaner().setImportComparator(new DefaultImportComparator()));
      printer.setIgnoreImplicit(false);
      printer.setPreprocessors(preprocessors);
      return printer;
    });
    spoon.buildModel();
  }

  public static String getRelativePath(CtExecutable<?> executable, String srcPath) {
    if (!executable.getPosition().isValidPosition() && !executable.getParent().getPosition().isValidPosition()) {
      System.out.printf("getRelativePath: No valid position found for %s %n", Spoon.getSimpleSignature(executable));
      return new NoSourcePosition().toString();
    }
    var srcURI = new File(srcPath).toURI();
    var absFile = executable.getPosition().getCompilationUnit().getFile();
    if (absFile == null) absFile = executable.getParent().getPosition().getCompilationUnit().getFile();
    return srcURI.relativize(absFile.toURI()).getPath();
  }

  public static String getUniqueName(CtExecutable<?> executable) {
    String simpleSignature = getSimpleSignature(executable);
    if (executable instanceof CtConstructor<?>) return String.format("%s.%s",
            ((CtConstructor<?>) executable).getDeclaringType().getQualifiedName(),
            simpleSignature);
    else return String.format("%s.%s", ((CtType<?>) executable.getParent()).getQualifiedName(), simpleSignature);
  }

  public static String getSimpleSignature(CtExecutable<?> executable) {
    SimpleSignaturePrinter pr = new SimpleSignaturePrinter();
    pr.scan(executable);
    return pr.getSignature();
  }


  public static String prettyPrint(CtExecutable<?> executable) {
    try {
      return executable.toString();
    } catch (Exception e) {
      System.out.printf("ERROR in prettyPrint: executable = %s%n %s%n", getSimpleSignature(executable), e.getMessage());
    }
    return getSimpleSignature(executable);
  }

  public static String prettyPrint(CtBlock<?> block) {
    try {
      return block.toString();
    } catch (Exception e) {
      System.out.printf("ERROR in prettyPrint: block = %s%n", e.getMessage());
    }
    return null;
  }

  public static boolean isMethodOrConstructor(CtExecutable<?> executable) {
    return (executable instanceof CtMethod) || (executable instanceof CtConstructor);
  }

  public Set<CtMethod<?>> getTestPreAndPostMethods(CtMethod<?> testMethod) {
    var refs = Stream.of("org.junit.Before",
                    "org.junit.BeforeClass",
                    "org.junit.After",
                    "org.junit.AfterClass",
                    "org.junit.jupiter.api.Before",
                    "org.junit.jupiter.api.BeforeClass",
                    "org.junit.jupiter.api.After",
                    "org.junit.jupiter.api.AfterClass")
            .map(refName -> spoon.getFactory().Type().createReference(refName))
            .toArray(CtTypeReference[]::new);
    return testMethod.getDeclaringType().getMethodsAnnotatedWith(refs);
  }

  public List<CtClass<?>> getAllTestClasses() {
    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    TypeFilter<CtClass<?>> isRealTestingClass = new TypeFilter<>(CtClass.class) {
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

  public List<CtMethod<?>> getTests() {
    var refs = Stream.of("org.junit.Test", "org.junit.jupiter.api.Test")
            .map(refName -> spoon.getFactory().Type().createReference(refName))
            .toArray(CtTypeReference[]::new);
    var testMethods = new ArrayList<CtMethod<?>>();
    for (var type : spoon.getModel().getAllTypes()) {
      testMethods.addAll(type.getMethodsAnnotatedWith(refs));
    }
    return testMethods;
  }

  public List<CtExecutable<?>> getExecutablesByName(Set<String> names, Set<String> paths, String srcPath) {
    TypeFilter<CtExecutable<?>> executableNameFilter = new TypeFilter<>(CtExecutable.class) {
      @Override
      public boolean matches(CtExecutable<?> ctExecutable) {
        if (!super.matches(ctExecutable)) return false;
        if (!isMethodOrConstructor(ctExecutable)) return false;
        if (!names.contains(getUniqueName(ctExecutable))) return false;
        return paths == null || paths.contains(getRelativePath(ctExecutable, srcPath));
      }
    };
    return spoon.getModel().getRootPackage().getElements(executableNameFilter);
  }

  public List<CtExecutable<?>> getExecutablesByFile(Set<String> files) {
    TypeFilter<CtExecutable<?>> executableFileFilter = new TypeFilter<>(CtExecutable.class) {
      @Override
      public boolean matches(CtExecutable<?> ctExecutable) {
        if (!super.matches(ctExecutable)) return false;
        if (!isMethodOrConstructor(ctExecutable)) return false;
        var executableFilePath = getRelativePath(ctExecutable, srcPath);
        return files.contains(executableFilePath);
      }
    };
    return spoon.getModel().getRootPackage().getElements(executableFileFilter);
  }

  public CtType<?> getType(Integer index) {
    ArrayList<CtType<?>> orgTypes = (ArrayList<CtType<?>>) this.spoon.getModel().getAllTypes();
    return orgTypes.get(index);
  }

  public boolean isTest(CtMethod<?> method) {
    var junit = this.spoon.getFactory().Type().createReference("org.junit.Test");
    var jupiter = this.spoon.getFactory().Type().createReference("org.junit.jupiter.api.Test");
    for (var annotation : method.getAnnotations()) {
      if (annotation.getAnnotationType().equals(junit) || annotation.getAnnotationType().equals(jupiter)) return true;
    }
    return false;
  }
}
