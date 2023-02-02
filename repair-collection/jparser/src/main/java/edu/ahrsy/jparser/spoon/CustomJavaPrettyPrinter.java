package edu.ahrsy.jparser.spoon;

import spoon.compiler.Environment;
import spoon.reflect.declaration.CtAnnotation;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtParameter;
import spoon.reflect.declaration.CtTypedElement;
import spoon.reflect.reference.CtArrayTypeReference;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.DefaultJavaPrettyPrinter;

public class CustomJavaPrettyPrinter extends DefaultJavaPrettyPrinter {
  public CustomJavaPrettyPrinter(Environment env) {
    super(env);
  }

  private <T> boolean isParameterWithImplicitType(CtParameter<T> parameter) {
    return parameter.getType() != null && !parameter.getType().isImplicit();
  }

  private <T> boolean isNotFirstParameter(CtParameter<T> parameter) {
    return parameter.getParent() != null && parameter.getParent().getParameters().indexOf(parameter) != 0;
  }

  public void writeCtParameterAnnotations(CtElement element) {
    for (CtAnnotation<?> annotation : element.getAnnotations()) {

      // if element is a type reference and the parent is a typed element
      // which contains exactly the same annotation, then we are certainly in this case:
      // @myAnnotation String myField
      // in which case the annotation is attached to the type and the variable
      // in that case, we only print the annotation once.
      if (element.isParentInitialized() &&
              element instanceof CtTypeReference &&
              (element.getParent() instanceof CtTypedElement) &&
              element.getParent().getAnnotations().contains(annotation)) {
        continue;
      }

      this.scan(annotation);
      // Changed this line
      getPrinterTokenWriter().writeSpace();
    }
  }

  @Override
  public <T> void visitCtParameter(CtParameter<T> parameter) {
    getElementPrinterHelper().writeComment(parameter);
    // Change this line compared to parent impl
    this.writeCtParameterAnnotations(parameter);
    getElementPrinterHelper().writeModifiers(parameter);
    if (parameter.isVarArgs()) {
      scan(((CtArrayTypeReference<T>) parameter.getType()).getComponentType());
      getPrinterTokenWriter().writeSeparator("...");
    } else if (parameter.isInferred() && this.env.getComplianceLevel() >= 11) {
      getPrinterTokenWriter().writeKeyword("var");
    } else {
      scan(parameter.getType());
    }
    // after an implicit type, there is no space because we dont print anything
    if (isParameterWithImplicitType(parameter) || isNotFirstParameter(parameter) || ignoreImplicit) {
      getPrinterTokenWriter().writeSpace();
    }
    getPrinterTokenWriter().writeIdentifier(parameter.getSimpleName());
  }
}
