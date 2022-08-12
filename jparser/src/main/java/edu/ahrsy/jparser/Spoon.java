package edu.ahrsy.jparser;

import com.github.difflib.DiffUtils;
import com.github.difflib.patch.AbstractDelta;
import com.github.difflib.patch.Patch;
import edu.ahrsy.jparser.entity.Hunk;
import edu.ahrsy.jparser.entity.MethodChange;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

public class Spoon {
  private final SpoonAPI spoon;
  public String srcPath;

  public Spoon(String srcPath, Integer complianceLevel) {
    this.srcPath = srcPath;
    spoon = new Launcher();
    spoon.addInputResource(srcPath);
    if (complianceLevel != null) spoon.getEnvironment().setComplianceLevel(complianceLevel);
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

  public static List<MethodChange> getMethodChanges(
          List<CtExecutable<?>> baseExecutables, List<CtExecutable<?>> headExecutables, String headSrcPath
  ) {
    var baseMethodsMap = baseExecutables.stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m));
    var methodChanges = new ArrayList<MethodChange>();
    for (var hMethod : headExecutables) {
      var hMethodName = Spoon.getUniqueName(hMethod);
      if (!baseMethodsMap.containsKey(hMethodName)) continue;

      var bMethodCode = prettyPrintWithoutComments(baseMethodsMap.get(hMethodName));
      var hMethodCode = prettyPrintWithoutComments(hMethod);
      if (bMethodCode.equals(hMethodCode)) continue;

      var methodFilePath = Spoon.getRelativePath(hMethod, headSrcPath);
      var methodChange = new MethodChange(methodFilePath, hMethodName);
      List<String> original = Arrays.asList(bMethodCode.split("\n"));
      List<String> revised = Arrays.asList(hMethodCode.split("\n"));
      Patch<String> patch = DiffUtils.diff(original, revised);
      for (AbstractDelta<String> delta : patch.getDeltas()) {
        methodChange.addHunk(Hunk.from(delta));
      }
      methodChanges.add(methodChange);
    }

    return methodChanges;
  }

  public static String prettyPrintWithoutComments(CtExecutable<?> executable) {
    var executableCopy = executable.clone();
    for (var comment : executable.getComments())
      executableCopy.removeComment(comment);
    return executableCopy.prettyprint();
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

  public List<CtExecutable<?>> getExecutablesByName(Set<String> names) {
    TypeFilter<CtExecutable<?>> executableNameFilter = new TypeFilter<>(CtExecutable.class) {
      @Override
      public boolean matches(CtExecutable<?> ctExecutable) {
        if (!super.matches(ctExecutable)) {
          return false;
        }
        return names.contains(getUniqueName(ctExecutable));
      }
    };
    return spoon.getModel().getRootPackage().getElements(executableNameFilter);
  }

  public List<CtExecutable<?>> getExecutablesByFile(Set<String> files, String srcPath) {
    TypeFilter<CtExecutable<?>> executableFileFilter = new TypeFilter<>(CtExecutable.class) {
      @Override
      public boolean matches(CtExecutable<?> ctExecutable) {
        if (!super.matches(ctExecutable)) {
          return false;
        }
        var executableFilePath = getRelativePath(ctExecutable, srcPath);
        return files.contains(executableFilePath);
      }
    };
    return spoon.getModel().getRootPackage().getElements(executableFileFilter);
  }
}
