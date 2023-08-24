package edu.ahrsy.jparser.entity.elements;

import edu.ahrsy.jparser.spoon.Spoon;
import spoon.reflect.code.*;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.*;
import spoon.support.reflect.declaration.InvisibleArrayConstructorImpl;

import java.util.Objects;
import java.util.stream.Collectors;

public class ElementValueHelper {
  public static String getValue(CtElement element) {
    // Executables
    if (element instanceof CtConstructor)
      return getValue((CtConstructor<?>) element);
    else if (element instanceof CtNewClass)
      return getValue((CtNewClass<?>) element);
    else if (element instanceof CtConstructorCall)
      return getValue((CtConstructorCall<?>) element);
    else if (element instanceof CtAnnotationMethod)
      return getValue((CtAnnotationMethod<?>) element);
    else if (element instanceof CtMethod)
      return getValue((CtMethod<?>) element);
    else if (element instanceof CtExecutableReference)
      return getValue((CtExecutableReference<?>) element);
    else if (element instanceof CtExecutableReferenceExpression)
      return getValue((CtExecutableReferenceExpression<?, ?>) element);
    else if (element instanceof CtInvocation)
      return getValue((CtInvocation<?>) element);
      // Arrays
    else if (element instanceof CtArrayRead)
      return getValue((CtArrayRead<?>) element);
    else if (element instanceof CtArrayWrite)
      return getValue((CtArrayWrite<?>) element);
    else if (element instanceof CtArrayTypeReference)
      return getValue((CtArrayTypeReference<?>) element);
    else if (element instanceof CtNewArray)
      return getValue((CtNewArray<?>) element);
      // Fields
    else if (element instanceof CtEnumValue)
      return getValue((CtEnumValue<?>) element);
    else if (element instanceof CtField)
      return getValue((CtField<?>) element);
    else if (element instanceof CtFieldReference)
      return getValue((CtFieldReference<?>) element);
    else if (element instanceof CtFieldRead)
      return getValue((CtFieldRead<?>) element);
    else if (element instanceof CtFieldWrite)
      return getValue((CtFieldWrite<?>) element);
      // Variables
    else if (element instanceof CtLocalVariable)
      return getValue((CtLocalVariable<?>) element);
    else if (element instanceof CtLocalVariableReference)
      return getValue((CtLocalVariableReference<?>) element);
    else if (element instanceof CtCatchVariable)
      return getValue((CtCatchVariable<?>) element);
    else if (element instanceof CtVariableWrite)
      return getValue((CtVariableWrite<?>) element);
    else if (element instanceof CtVariableRead)
      return getValue((CtVariableRead<?>) element);
      // Parameters
    else if (element instanceof CtParameter)
      return getValue((CtParameter<?>) element);
    else if (element instanceof CtParameterReference)
      return getValue((CtParameterReference<?>) element);
      // Expressions
    else if (element instanceof CtLiteral)
      return getValue((CtLiteral<?>) element);
    else if (element instanceof CtThrow)
      return getValue((CtThrow) element);
      // Types
    else if (element instanceof CtInterface)
      return getValue((CtInterface<?>) element);
    else if (element instanceof CtEnum)
      return getValue((CtEnum<?>) element);
    else if (element instanceof CtClass)
      return getValue((CtClass<?>) element);
    else if (element instanceof CtAnnotationType)
      return getValue((CtAnnotationType<?>) element);
    else if (element instanceof CtTypeReference)
      return getValue((CtTypeReference<?>) element);
    else if (element instanceof CtTypeAccess)
      return getValue((CtTypeAccess<?>) element);
    else if (element instanceof CtAnnotation)
      return getValue((CtAnnotation<?>) element);
    return null;
  }

  private static String referenceToString(CtReference reference) {
    try {
      return reference.toString();
    } catch (Exception e) {
      return null;
    }
  }

  private static boolean isValidDeclaration(CtElement element) {
    if (element instanceof InvisibleArrayConstructorImpl)
      return false;
    return element != null;
  }

  private static String getValue(CtTypeReference<?> reference) {
    if (reference instanceof CtTypeParameterReference)
      return null;
    var declaration = reference.getTypeDeclaration();
    return isValidDeclaration(declaration) ? getValue(declaration) : reference.getQualifiedName();
  }

  private static String getValue(CtVariableReference<?> reference) {
    var declaration = reference.getDeclaration();
    if (isValidDeclaration(declaration))
      return getValue(declaration);
    else {
      var type = reference.getType();
      return String.format("%s %s", type != null ? getValue(type) : "<unknown>", reference.getSimpleName());
    }
  }

  private static String getValue(CtExecutableReference<?> reference) {
    var declaration = reference.getExecutableDeclaration();
    return isValidDeclaration(declaration) ? getValue(declaration) : referenceToString(reference);
  }

  private static String getValue(CtExecutable<?> element) {
    return Spoon.getUniqueName(element);
  }

  private static String getValue(CtAbstractInvocation<?> element) {
    return getValue(element.getExecutable());
  }

  private static String getValue(CtExecutableReferenceExpression<?, ?> element) {
    return getValue(element.getExecutable());
  }

  private static String getValue(CtNewClass<?> element) {
    return getValue((CtConstructorCall<?>) element);
  }

  private static String getValue(CtArrayAccess<?, ?> element) {
    return getValue(element.getTarget());
  }

  private static String getValue(CtVariable<?> element) {
    var type = element.getType();
    return String.format("%s %s", type != null ? getValue(type) : "<unknown>", element.getSimpleName());
  }

  private static String getValue(CtCatchVariable<?> element) {
    return String.format("%s %s",
        element.getMultiTypes().stream().map(ElementValueHelper::getValue).collect(Collectors.joining(" | ")),
        element.getSimpleName());
  }

  private static String getValue(CtVariableAccess<?> element) {
    if (element instanceof CtSuperAccess)
      return null;
    return getValue(element.getVariable());
  }

  private static String getValue(CtType<?> element) {
    return element.getQualifiedName();
  }

  private static String getValue(CtLiteral<?> element) {
    return String.format("%s '%s'", getValue(element.getType()), element.getValue());
  }

  private static String getValue(CtTypeAccess<?> element) {
    return getValue(element.getAccessedType());
  }

  private static String getValue(CtAnnotation<?> element) {
    return getValue(element.getAnnotationType());
  }

  private static String getValue(CtNewArray<?> element) {
    var type = element.getType();
    if (type == null) {
      var expressions = element.getElements();
      return expressions.size() > 0 ? getValue(expressions.get(0)) : null;
    }
    return getValue(type);
  }

  private static String getValue(CtThrow element) {
    return getValue(element.getThrownExpression());
  }
}
