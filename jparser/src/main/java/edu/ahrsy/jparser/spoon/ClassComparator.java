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
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.TypeFilter;
import spoon.support.sniper.SniperJavaPrettyPrinter;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.stream.Collectors;

public class ClassComparator {
  private final Spoon bSpoon;
  private final Spoon aSpoon;
  private final Diff diff;

  public ClassComparator(String bSrcPath, String aSrcPath, Integer complianceLevel) {
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

  public CtType<?> applyPatchAndSave(CtType<?> type, CtMethod<?> patchedMethod) {
    var beforePatch = IOUtils.readFile(Path.of(type.getPosition().getFile().getPath()));
    var oldMethod = type.getElements(new TypeFilter<>(CtMethod.class) {
      @Override
      public boolean matches(CtMethod method) {
        return method.getSignature().equals(patchedMethod.getSignature());
      }
    }).get(0);
    var stringBuilder = new StringBuilder(beforePatch);
    var start = oldMethod.getPosition().getSourceStart();
    var end = oldMethod.getPosition().getSourceEnd();
    // TODO get output path and save this afterPatch
    var afterPatch = stringBuilder.replace(start, end + 1, Spoon.prettyPrint(patchedMethod)).toString();
    return type;
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

  public List<MethodChange> getSingleHunkMethodChanges(ChangedTestClass changedTestClass) {
    // TODO this condition can be removed
    if (!onlyTestsChanged()) return Collections.emptyList();

    var changedTests = getChangedTests();
    var testChanges = new ArrayList<MethodChange>();
    for (var test : changedTests) {
      // applyPatchAndSave(aSpoon.createCopy().getType(0), test.getLeft());
      var name = Spoon.getUniqueName(test.getLeft());
      var change = new MethodChange(changedTestClass.beforePath, name);
      change.extractHunks(Spoon.prettyPrint(test.getLeft()), Spoon.prettyPrint(test.getRight()));
      if (change.getHunks().size() == 1) testChanges.add(change);
    }
    return testChanges;
  }
}
