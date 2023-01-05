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
import java.util.stream.IntStream;
import java.util.stream.Stream;

public class Spoon {
  private final SpoonAPI spoon;
  public String srcPath;
  private List<CtMethod<?>> testMethods = null;

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

  public static String getRelativePath(CtNamedElement element, String srcPath) {
    if (!element.getPosition().isValidPosition() && !element.getParent().getPosition().isValidPosition()) {
      System.out.printf("getRelativePath: No valid position found for %s %n", element.getSimpleName());
      return new NoSourcePosition().toString();
    }
    var srcURI = new File(srcPath).toURI();
    var absFile = element.getPosition().getCompilationUnit().getFile();
    if (absFile == null) absFile = element.getParent().getPosition().getCompilationUnit().getFile();
    return srcURI.relativize(absFile.toURI()).getPath();
  }

  public static String getParentQualifiedName(CtExecutable<?> executable) {
    if (executable instanceof CtConstructor<?>)
      return ((CtConstructor<?>) executable).getDeclaringType().getQualifiedName();
    else return ((CtType<?>) executable.getParent()).getQualifiedName();
  }

  public static String getUniqueName(CtExecutable<?> executable) {
    String simpleSignature = getSimpleSignature(executable);
    String parentQualifiedName = getParentQualifiedName(executable);
    return String.format("%s.%s", parentQualifiedName, simpleSignature);
  }

  public static String getSimpleSignature(CtExecutable<?> executable) {
    SimpleSignaturePrinter pr = new SimpleSignaturePrinter();
    pr.scan(executable);
    return pr.getSignature();
  }


  public static String prettyPrint(CtNamedElement element) {
    try {
      return element.toString();
    } catch (Exception e) {
      System.out.printf("ERROR in prettyPrint: executable = %s%n %s%n", element.getSimpleName(), e.getMessage());
    }
    return element.getSimpleName();
  }

  // TODO check whether comments are included. If yes (better not be), remove them and handle diff hunks!
  public static String print(CtNamedElement element) {
    var srcFile = getOriginalSourceCode(element);
    var elementStart = element.getPosition().getSourceStart();
    var elementEnd = element.getPosition().getSourceEnd();
    return srcFile.substring(elementStart, elementEnd + 1);
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
    return ((executable instanceof CtMethod) || (executable instanceof CtConstructor)) &&
            executable.getPosition().isValidPosition();
  }

  public static boolean codeIsModified(CtNamedElement src, CtNamedElement dst) {
    if (src == null || dst == null) return true;
    var srcCode = Spoon.prettyPrint(src);
    var dstCode = Spoon.prettyPrint(dst);
    return !srcCode.equals(dstCode);
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
    if (this.testMethods != null) return this.testMethods;

    var refs = Stream.of("org.junit.Test", "org.junit.jupiter.api.Test")
            .map(refName -> spoon.getFactory().Type().createReference(refName))
            .toArray(CtTypeReference[]::new);
    this.testMethods = new ArrayList<>();
    for (var type : spoon.getModel().getAllTypes()) {
      this.testMethods.addAll(type.getMethodsAnnotatedWith(refs));
    }
    return this.testMethods;
  }

  public List<CtExecutable<?>> getExecutablesByName(Set<String> names, Set<String> paths) {
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

  public static String getOriginalSourceCode(CtNamedElement element) {
    return element.getPosition().getCompilationUnit().getOriginalSourceCode();
  }

  public static Integer getStartLine(CtNamedElement element) {
    var sourceStart = element.getPosition().getSourceStart();
    var lineSepPos = element.getPosition().getCompilationUnit().getLineSeparatorPositions();
    return IntStream.range(0, lineSepPos.length).filter(i -> sourceStart < lineSepPos[i]).findFirst().orElseThrow() + 1;
  }

  public CtType<?> getTopLevelTypeByFile(String file) {
    TypeFilter<CtType<?>> typeFileFilter = new TypeFilter<>(CtType.class) {
      @Override
      public boolean matches(CtType<?> ctType) {
        if (!super.matches(ctType)) return false;
        if (!ctType.isTopLevel()) return false;
        if (!ctType.getPosition().isValidPosition()) return false;
        var typeFile = getRelativePath(ctType, srcPath);
        return typeFile.equals(file);
      }
    };
    return spoon.getModel().getRootPackage().getElements(typeFileFilter).get(0);
  }
}
