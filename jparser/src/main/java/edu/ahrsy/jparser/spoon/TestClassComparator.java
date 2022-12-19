package edu.ahrsy.jparser.spoon;

import edu.ahrsy.jparser.entity.ChangedTestClass;
import edu.ahrsy.jparser.entity.MethodChange;
import edu.ahrsy.jparser.utils.IOUtils;
import gumtree.spoon.AstComparator;
import gumtree.spoon.diff.Diff;
import gumtree.spoon.diff.operations.Operation;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtMethod;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.stream.Collectors;
import java.util.stream.IntStream;

public class TestClassComparator {
  private final Spoon bSpoon;
  private final Spoon aSpoon;
  private final Diff diff;

  public TestClassComparator(String bSrcPath, String aSrcPath, Integer complianceLevel) {
    this.bSpoon = new Spoon(bSrcPath, complianceLevel);
    this.aSpoon = new Spoon(aSrcPath, complianceLevel);
    this.diff = new AstComparator().compare(bSpoon.getType(0), aSpoon.getType(0));
  }

  private CtMethod<?> getParentMethod(CtElement element) {
    if (element == null) return null;
    if (element instanceof CtMethod) return (CtMethod<?>) element;
    return element.getParent(CtMethod.class);
  }

  private boolean isInsideMethod(Operation<?> op) {
    return !(op.getSrcNode() instanceof CtMethod) && (getParentMethod(op.getSrcNode()) != null);
  }

  private boolean codeModification(CtMethod<?> src, CtMethod<?> dst) {
    if (src == null || dst == null) return true;
    var srcCode = Spoon.prettyPrint(src);
    var dstCode = Spoon.prettyPrint(dst);
    if (srcCode == null || dstCode == null) return true;
    return !srcCode.equals(dstCode);
  }

  public boolean onlyTestsChanged() {
    if (this.diff.getRootOperations().size() == 0) return false;
    for (var op : this.diff.getRootOperations()) {
      var srcParent = getParentMethod(op.getSrcNode());
      var dstParent = getParentMethod(op.getDstNode());
      if (!isInsideMethod(op) || !this.bSpoon.isTest(srcParent) || !codeModification(srcParent, dstParent))
        return false;
    }
    return true;
  }

  public String replaceChangedTestWithOriginal(CtMethod<?> original, CtMethod<?> changed) {
    var originalSrcFile = Spoon.readSourceFile(original.getTopLevelType());
    var originalStart = original.getPosition().getSourceStart();
    var originalEnd = original.getPosition().getSourceEnd();
    var originalSrc = originalSrcFile.substring(originalStart, originalEnd + 1);

    var changedSrcFile = new StringBuilder(Spoon.readSourceFile(changed.getTopLevelType()));
    var changedStart = changed.getPosition().getSourceStart();
    var changedEnd = changed.getPosition().getSourceEnd();
    return changedSrcFile.replace(changedStart, changedEnd + 1, originalSrc).toString();
  }

  public List<Pair<CtMethod<?>, CtMethod<?>>> getChangedTests() {
    var changedTests = new HashMap<String, Pair<CtMethod<?>, CtMethod<?>>>();
    var bTests = bSpoon.getTests().stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m));
    for (var aTest : aSpoon.getTests()) {
      var name = Spoon.getUniqueName(aTest);
      if (bTests.containsKey(name) && codeModification(bTests.get(name), aTest))
        changedTests.put(name, new ImmutablePair<>(bTests.get(name), aTest));
    }
    return new ArrayList<>(changedTests.values());
  }

  private Integer getStartLine(CtMethod<?> method) {
    var sourceStart = method.getPosition().getSourceStart();
    var lineSepPos = method.getPosition().getCompilationUnit().getLineSeparatorPositions();
    return IntStream.range(0, lineSepPos.length).filter(i -> sourceStart < lineSepPos[i]).findFirst().orElseThrow() + 1;
  }

  public List<MethodChange> getSingleHunkMethodChanges(ChangedTestClass changedTestClass, String outputPath) {
    // TODO this condition can be removed
    if (!onlyTestsChanged()) return Collections.emptyList();

    var changedTests = getChangedTests();
    var testChanges = new ArrayList<MethodChange>();
    for (var test : changedTests) {
      var name = Spoon.getUniqueName(test.getLeft());
      var change = new MethodChange(changedTestClass.beforePath, name);
      change.extractHunks(Spoon.prettyPrint(test.getLeft()), Spoon.prettyPrint(test.getRight()));
      change.applyHunkLineNoOffset(getStartLine(test.getLeft()), getStartLine(test.getRight()));
      if (change.getHunks().size() == 1) {
        testChanges.add(change);
        var brokenPatch = replaceChangedTestWithOriginal(test.getLeft(), test.getRight());
        var outputFile = Path.of(outputPath,
                "brokenPatches",
                changedTestClass.afterCommit,
                test.getLeft().getTopLevelType().getSimpleName(),
                test.getLeft().getSimpleName(),
                changedTestClass.afterPath);
        IOUtils.saveFile(outputFile, brokenPatch);
      }
    }
    return testChanges;
  }
}
