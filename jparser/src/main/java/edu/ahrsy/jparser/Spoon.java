package edu.ahrsy.jparser;

import edu.ahrsy.jparser.cli.Command;
import spoon.Launcher;
import spoon.SpoonAPI;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.util.LinkedList;
import java.util.List;
import java.util.Set;

public class Spoon {
  private static SpoonAPI spoon;

  public static List<CtClass<?>> getAllTestClasses() {
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

  public static List<CtMethod<?>> getTestMethods() {
    CtTypeReference<?> juTestRef = spoon.getFactory().Type().createReference("org.junit.Test");
    var testMethods = new LinkedList<CtMethod<?>>();
    for (var type : spoon.getModel().getAllTypes()) {
      testMethods.addAll(type.getMethodsAnnotatedWith(juTestRef));
    }
    return testMethods;
  }

  public static List<CtMethod<?>> getMethodsByName(Set<String> names) {
    TypeFilter<CtMethod<?>> isRepairedMethod =
            new TypeFilter<>(CtMethod.class) {
              @Override
              public boolean matches(CtMethod<?> ctMethod) {
                if (!super.matches(ctMethod)) {
                  return false;
                }
                var signature = String.format("%s.%s",
                        ctMethod.getDeclaringType().getQualifiedName(),
                        ctMethod.getSignature());
                return names.contains(signature);
              }
            };
    return spoon.getModel().getRootPackage().getElements(isRepairedMethod);
  }

  public static void initializeSpoon(Command cmd) {
    spoon = new Launcher();
    spoon.addInputResource(cmd.srcPath);
    if (cmd.complianceLevel != null)
      spoon.getEnvironment().setComplianceLevel(cmd.complianceLevel);
    spoon.buildModel();
  }
}
