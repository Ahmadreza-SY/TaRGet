package edu.ahrsy.jparser.spoon;

import spoon.reflect.declaration.CtAnnotationMethod;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtParameter;
import spoon.reflect.reference.*;
import spoon.reflect.visitor.CtScanner;

/**
 * Copied from SPOON library.
 * Changed all qualified names to simple names.
 * Could not extend the SignaturePrinter class due to some private fields and methods.
 */
public class SimpleSignaturePrinter extends CtScanner {

  private final StringBuilder signature = new StringBuilder();

  public SimpleSignaturePrinter() {
  }

  public String getSignature() {
    return signature.toString();
  }

  @Override
  public <T> void visitCtArrayTypeReference(CtArrayTypeReference<T> reference) {
    scan(reference.getComponentType());
    write("[]");
  }

  @Override
  public <T> void visitCtExecutableReference(CtExecutableReference<T> reference) {
    writeNameAndParameters(reference);
  }

  /**
   * writes only the name and parameters' types
   */
  public <T> void writeNameAndParameters(CtExecutableReference<T> reference) {
    if (reference.isConstructor()) {
      write(reference.getDeclaringType().getSimpleName());
    } else {
      write(reference.getSimpleName());
    }
    write("(");
    if (!reference.getParameters().isEmpty()) {
      for (CtTypeReference<?> param : reference.getParameters()) {
        if (param != null && !"null".equals(param.getSimpleName())) {
          scan(param);
        } else {
          write(CtExecutableReference.UNKNOWN_TYPE);
        }
        write(",");
      }
      if (!reference.getParameters().isEmpty()) {
        clearLast(); // ","
      }
    }
    write(")");
  }

  @Override
  public <T> void visitCtTypeReference(CtTypeReference<T> reference) {
    write(reference.getSimpleName());
  }

  @Override
  public void visitCtTypeParameterReference(CtTypeParameterReference ref) {
    /*
     * signature doesn't contain name of type parameter reference,
     * because these three methods declarations:
     * 	<T extends String> void m(T a);
     * 	<S extends String> void m(S b);
     * 	void m(String c)
     * Should have the same signature.
     */
    scan(ref.getBoundingType());
  }

  @Override
  public void visitCtWildcardReference(CtWildcardReference ref) {
    write(ref.getSimpleName());
    if (!ref.isDefaultBoundingType() || !ref.getBoundingType().isImplicit()) {
      if (ref.isUpper()) {
        write(" extends ");
      } else {
        write(" super ");
      }
      scan(ref.getBoundingType());
    }
  }

  @Override
  public <T> void visitCtIntersectionTypeReference(CtIntersectionTypeReference<T> reference) {
    for (CtTypeReference<?> bound : reference.getBounds()) {
      scan(bound);
      write(",");
    }
    clearLast();
  }

  @Override
  public <T> void visitCtConstructor(CtConstructor<T> c) {
    if (c.getDeclaringType() != null) {
      write(c.getDeclaringType().getSimpleName());
    }
    write("(");
    for (CtParameter<?> p : c.getParameters()) {
      scan(p.getType());
      write(",");
    }
    if (!c.getParameters().isEmpty()) {
      clearLast();
    }
    write(")");
  }

  @Override
  public <T> void visitCtAnnotationMethod(CtAnnotationMethod<T> annotationMethod) {
    visitCtMethod(annotationMethod);
  }

  /**
   * For methods, this implementation of signature contains the return type, which corresponds
   * to what the Java compile and virtual machine call a "descriptor".
   * <p>
   * See chapter "8.4.2 Method Signature" of the Java specification
   */
  @Override
  public <T> void visitCtMethod(CtMethod<T> m) {
    write(m.getSimpleName());
    write("(");
    for (CtParameter<?> p : m.getParameters()) {
      scan(p.getType());
      write(",");
    }
    if (!m.getParameters().isEmpty()) {
      clearLast();
    }
    write(")");
  }

  private void clearLast() {
    signature.deleteCharAt(signature.length() - 1);
  }

  protected void write(String value) {
    signature.append(value);
  }
}
