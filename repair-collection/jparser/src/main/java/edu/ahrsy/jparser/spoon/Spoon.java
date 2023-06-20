package edu.ahrsy.jparser.spoon;

import edu.ahrsy.jparser.entity.TestElements;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.SpoonModelBuilder;
import spoon.processing.Processor;
import spoon.reflect.code.CtComment;
import spoon.reflect.cu.position.NoSourcePosition;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtExecutableReference;
import spoon.reflect.reference.CtReference;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.DefaultImportComparator;
import spoon.reflect.visitor.ForceImportProcessor;
import spoon.reflect.visitor.ImportCleaner;
import spoon.reflect.visitor.ImportConflictDetector;
import spoon.reflect.visitor.filter.AbstractFilter;
import spoon.reflect.visitor.filter.TypeFilter;
import spoon.support.compiler.FileSystemFolder;
import spoon.support.compiler.FilteringFolder;

import java.io.File;
import java.util.*;
import java.util.stream.Collectors;
import java.util.stream.IntStream;
import java.util.stream.Stream;

public class Spoon {
  private final SpoonAPI spoon;
  public String srcPath;
  private List<CtMethod<?>> testMethods = null;

  public Spoon(String srcPath, Integer complianceLevel) {
    this.srcPath = srcPath;
    spoon = new Launcher();
    if (new File(srcPath).isDirectory()) {
      SpoonModelBuilder modelBuilder = ((Launcher) spoon).getModelBuilder();
      FilteringFolder resources = new FilteringFolder();
      resources.addFolder(new FileSystemFolder(srcPath));
      resources.removeAllThatMatch(".*/package-info.java");
      resources.removeAllThatMatch(".*/module-info.java");
      modelBuilder.addInputSource(resources);
    } else
      spoon.addInputResource(srcPath);
    spoon.getEnvironment().setIgnoreDuplicateDeclarations(true);
    if (complianceLevel != null) spoon.getEnvironment().setComplianceLevel(complianceLevel);
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
    try {
      spoon.buildModel();
      spoon.getEnvironment().setCommentEnabled(false);
    } catch (Exception e) {
      System.err.printf("%nAn exception occured while parsing source path by Spoon: %s%nERROR: %s%n", srcPath,
          e.getMessage());
      throw e;
    }
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
      // System.out.printf("ERROR in prettyPrint: executable = %s%n %s%n", element.getSimpleName(), e.getMessage());
    }
    return element.getSimpleName();
  }

  public static String print(CtNamedElement element) {
    var srcFile = getOriginalSourceCode(element);
    var elementStart = element.getPosition().getSourceStart();
    var elementEnd = element.getPosition().getSourceEnd();
    return srcFile.substring(elementStart, elementEnd + 1);
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

  private static boolean hasDeclarationAndPosition(CtReference reference) {
    var declaration = reference.getDeclaration();
    if (declaration == null)
      return false;
    return declaration.getPosition().isValidPosition();
  }

  public static TestElements getElements(CtMethod<?> method) {
    var types = method.getElements(new AbstractFilter<CtTypeReference<?>>() {
      @Override
      public boolean matches(CtTypeReference<?> reference) {
        return hasDeclarationAndPosition(reference) && super.matches(reference);
      }
    }).stream().map(r -> r.getDeclaration().getQualifiedName()).distinct().collect(Collectors.toList());

    var executables = method.getElements(new AbstractFilter<CtExecutableReference<?>>() {
      @Override
      public boolean matches(CtExecutableReference<?> reference) {
        return hasDeclarationAndPosition(reference) && super.matches(reference);
      }
    }).stream().map(r -> getUniqueName(r.getDeclaration())).distinct().collect(Collectors.toList());

    return new TestElements(types, executables);
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

  public static Integer getStartLine(CtElement element) {
    if (element == null) return 0;
    var sourceStart = element.getPosition().getSourceStart();
    return getPositionLine(element, sourceStart);
  }

  public static Integer getEndLine(CtElement element) {
    if (element == null) return 0;
    var sourceEnd = element.getPosition().getSourceEnd();
    return getPositionLine(element, sourceEnd);
  }

  private static Integer getPositionLine(CtElement element, Integer position) {
    var lineSepPos = element.getPosition().getCompilationUnit().getLineSeparatorPositions();
    return IntStream.range(0, lineSepPos.length)
        .filter(i -> position < lineSepPos[i])
        .findFirst()
        .orElse(lineSepPos.length) + 1;
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
    var elements = spoon.getModel().getRootPackage().getElements(typeFileFilter);
    return elements.isEmpty() ? null : elements.get(0);
  }

  public CtType<?> getTopLevelType() {
    TypeFilter<CtType<?>> typeFileFilter = new TypeFilter<>(CtType.class) {
      @Override
      public boolean matches(CtType<?> ctType) {
        if (!super.matches(ctType)) return false;
        if (!ctType.getPosition().isValidPosition()) return false;
        return ctType.isTopLevel();
      }
    };
    var elements = spoon.getModel().getRootPackage().getElements(typeFileFilter);
    return elements.isEmpty() ? null : elements.get(0);
  }

  public static Set<Integer> getCommentsLineNumbers(CtNamedElement element) {
    if (element == null) return Collections.emptySet();
    List<CtComment> comments = element.getElements(new TypeFilter<>(CtComment.class));
    if (comments.isEmpty()) return Collections.emptySet();

    var commentsLineNumbers = new HashSet<Integer>();
    for (var comment : comments) {
      var commentLines = IntStream.rangeClosed(getStartLine(comment), getEndLine(comment))
          .boxed()
          .collect(Collectors.toList());
      commentsLineNumbers.addAll(commentLines);
    }
    return commentsLineNumbers;
  }
}
