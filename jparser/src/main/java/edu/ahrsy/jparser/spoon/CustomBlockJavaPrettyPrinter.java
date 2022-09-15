package edu.ahrsy.jparser.spoon;

import spoon.compiler.Environment;
import spoon.reflect.code.CtBlock;
import spoon.reflect.code.CtStatement;
import spoon.reflect.visitor.DefaultJavaPrettyPrinter;

public class CustomBlockJavaPrettyPrinter extends DefaultJavaPrettyPrinter {
  public CustomBlockJavaPrettyPrinter(Environment env) {
    super(env);
  }

  @Override
  public <R> void visitCtBlock(CtBlock<R> block) {
    // Print nested blocks normally
    if (block.getParent() instanceof CtBlock) {
      super.visitCtBlock(block);
      return;
    }

    // Removed indentation and curly brackets from the super method
    enterCtStatement(block);
    for (CtStatement statement : block.getStatements()) {
      if (!statement.isImplicit()) {
        getPrinterTokenWriter().writeln();
        getElementPrinterHelper().writeStatement(statement);
      }
    }
    getPrinterTokenWriter().getPrinterHelper().adjustEndPosition(block);
    exitCtStatement(block);
  }
}
