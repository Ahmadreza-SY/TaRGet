package edu.ahrsy.jparser;

import edu.ahrsy.jparser.entity.ChangedTestClass;
import edu.ahrsy.jparser.entity.Change;
import edu.ahrsy.jparser.entity.SingleHunkTestChange;
import edu.ahrsy.jparser.entity.TestSource;
import edu.ahrsy.jparser.gumtree.GumTreeUtils;
import edu.ahrsy.jparser.refactoringminer.RefactoringMinerAPI;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import gumtree.spoon.AstComparator;
import gumtree.spoon.diff.Diff;
import gumtree.spoon.diff.operations.Operation;
import org.apache.commons.lang3.tuple.ImmutablePair;
import org.apache.commons.lang3.tuple.Pair;
import org.refactoringminer.api.RefactoringType;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtMethod;

import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

public class TestClassComparator {
  private final Spoon bSpoon;
  private final Spoon aSpoon;

  public TestClassComparator(String bSrcPath, String aSrcPath, Integer complianceLevel) {
    this.bSpoon = new Spoon(bSrcPath, complianceLevel);
    this.aSpoon = new Spoon(aSrcPath, complianceLevel);
  }

  private CtMethod<?> getParentMethod(CtElement element) {
    if (element == null) return null;
    if (element instanceof CtMethod) return (CtMethod<?>) element;
    return element.getParent(CtMethod.class);
  }

  private boolean isInsideMethod(Operation<?> op) {
    return !(op.getSrcNode() instanceof CtMethod) && (getParentMethod(op.getSrcNode()) != null);
  }

  public boolean onlyTestsChanged() {
    Diff diff = new AstComparator().compare(bSpoon.getType(0), aSpoon.getType(0));
    if (diff.getRootOperations().size() == 0) return false;
    for (var op : diff.getRootOperations()) {
      var srcParent = getParentMethod(op.getSrcNode());
      var dstParent = getParentMethod(op.getDstNode());
      if (!isInsideMethod(op) || !this.bSpoon.isTest(srcParent) || !Spoon.codeIsModified(srcParent, dstParent))
        return false;
    }
    return true;
  }

  public String replaceChangedTestWithOriginal(CtMethod<?> original, CtMethod<?> changed) {
    var originalSrcFile = Spoon.getOriginalSourceCode(original.getTopLevelType());
    var originalStart = original.getPosition().getSourceStart();
    var originalEnd = original.getPosition().getSourceEnd();
    var originalSrc = originalSrcFile.substring(originalStart, originalEnd + 1);

    var changedSrcFile = new StringBuilder(Spoon.getOriginalSourceCode(changed.getTopLevelType()));
    var changedStart = changed.getPosition().getSourceStart();
    var changedEnd = changed.getPosition().getSourceEnd();
    return changedSrcFile.replace(changedStart, changedEnd + 1, originalSrc).toString();
  }

  private List<Pair<CtMethod<?>, CtMethod<?>>> getChangedTests() {
    var changedTests = new HashMap<String, Pair<CtMethod<?>, CtMethod<?>>>();
    var bTests = bSpoon.getTests().stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m));
    for (var aTest : aSpoon.getTests()) {
      var name = Spoon.getUniqueName(aTest);
      if (bTests.containsKey(name) && Spoon.codeIsModified(bTests.get(name), aTest))
        changedTests.put(name, new ImmutablePair<>(bTests.get(name), aTest));
    }
    return new ArrayList<>(changedTests.values());
  }

  private TestSource getTestSource(String name, Spoon spoon) {
    var method = spoon.getTests()
        .stream()
        .filter(tm -> Spoon.getUniqueName(tm).equals(name))
        .findFirst()
        .orElseThrow();
    return TestSource.from(method);
  }

  public TestSource getBeforeTestSource(String name) {
    return getTestSource(name, bSpoon);
  }

  public TestSource getAfterTestSource(String name) {
    return getTestSource(name, aSpoon);
  }

  public List<SingleHunkTestChange> getSingleHunkTestChanges(ChangedTestClass testClass, String outputPath) {
    var changedTests = getChangedTests();
    if (changedTests.isEmpty()) return Collections.emptyList();
    // TODO this condition can be removed
    if (!onlyTestsChanged()) return Collections.emptyList();

    Map<String, List<RefactoringType>> refactorings = RefactoringMinerAPI.mineMethodRefactorings(bSpoon.srcPath,
        aSpoon.srcPath);
    var testChanges = new ArrayList<SingleHunkTestChange>();
    for (var test : changedTests) {
      var testName = Spoon.getUniqueName(test.getLeft());
      var change = new Change(testClass.beforePath, testClass.afterPath, testName);
      change.extractHunks(test.getLeft(), test.getRight());
      if (change.getHunks().size() == 1) {
        var singleHunkChange = new SingleHunkTestChange(testName,
            getBeforeTestSource(testName),
            getAfterTestSource(testName),
            testClass.beforePath,
            testClass.afterPath,
            testClass.beforeCommit,
            testClass.afterCommit,
            change.getHunks().get(0),
            GumTreeUtils.getASTActions(test.getLeft(), test.getRight()),
            refactorings.getOrDefault(testName, Collections.emptyList()));
        testChanges.add(singleHunkChange);
        var brokenPatch = replaceChangedTestWithOriginal(test.getLeft(), test.getRight());
        var outputFile = Path.of(outputPath,
            "codeMining",
            "brokenPatches",
            testClass.afterCommit,
            test.getLeft().getTopLevelType().getSimpleName(),
            test.getLeft().getSimpleName(),
            testClass.afterPath);
        IOUtils.saveFile(outputFile, brokenPatch);
      }
    }
    return testChanges;
  }
}
