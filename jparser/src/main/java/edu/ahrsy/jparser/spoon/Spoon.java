package edu.ahrsy.jparser.spoon;

import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.processing.Processor;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.DefaultImportComparator;
import spoon.reflect.visitor.ForceImportProcessor;
import spoon.reflect.visitor.ImportCleaner;
import spoon.reflect.visitor.ImportConflictDetector;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;

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
    var srcURI = new File(srcPath).toURI();
    var absFile = executable.getPosition().getCompilationUnit().getFile();
    if (absFile == null) absFile = executable.getParent().getPosition().getCompilationUnit().getFile();
    return srcURI.relativize(absFile.toURI()).getPath();
  }

  public static String getUniqueName(CtExecutable<?> executable) {
    if (executable instanceof CtConstructor<?>) return executable.getSignature();
    return String.format("%s.%s", ((CtType<?>) executable.getParent()).getQualifiedName(), executable.getSignature());
  }

  public static String getSimpleName(CtExecutable<?> executable) {
    SimpleSignaturePrinter pr = new SimpleSignaturePrinter();
    pr.scan(executable);
    return pr.getSignature();
  }


  public static String prettyPrintWithoutComments(CtExecutable<?> executable) {
    return executable.toString();
  }

  public static boolean isMethodOrConstructor(CtExecutable<?> executable) {
    return (executable instanceof CtMethod) || (executable instanceof CtConstructor);
  }

  public Set<CtMethod<?>> getTestPreAndPostMethods(CtMethod<?> testMethod) {
    List<CtTypeReference<?>> refs = Arrays.asList(spoon.getFactory().Type().createReference("org.junit.Before"),
            spoon.getFactory().Type().createReference("org.junit.BeforeClass"),
            spoon.getFactory().Type().createReference("org.junit.After"),
            spoon.getFactory().Type().createReference("org.junit.AfterClass"));

    return testMethod.getDeclaringType().getMethodsAnnotatedWith(refs.toArray(new CtTypeReference[0]));
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

  public List<CtMethod<?>> getTestMethods() {
    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    var testMethods = new ArrayList<CtMethod<?>>();
    for (var type : spoon.getModel().getAllTypes()) {
      testMethods.addAll(type.getMethodsAnnotatedWith(juTestRef));
    }
    return testMethods;
  }

  public List<CtExecutable<?>> getExecutablesByName(Set<String> names, Set<String> paths, String srcPath) {
    TypeFilter<CtExecutable<?>> executableNameFilter = new TypeFilter<>(CtExecutable.class) {
      @Override
      public boolean matches(CtExecutable<?> ctExecutable) {
        if (!super.matches(ctExecutable)) return false;
        if (!isMethodOrConstructor(ctExecutable)) return false;
        if (paths != null && !paths.contains(getRelativePath(ctExecutable, srcPath))) return false;
        return names.contains(getUniqueName(ctExecutable));
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
}
