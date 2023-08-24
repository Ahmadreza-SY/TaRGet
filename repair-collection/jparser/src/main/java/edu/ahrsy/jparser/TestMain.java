package edu.ahrsy.jparser;

import com.google.gson.reflect.TypeToken;
import edu.ahrsy.jparser.entity.*;
import edu.ahrsy.jparser.entity.elements.ElementInfo;
import edu.ahrsy.jparser.entity.elements.ElementValueHelper;
import edu.ahrsy.jparser.entity.elements.SampleTest;
import edu.ahrsy.jparser.entity.elements.Test;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.GitAPI;
import edu.ahrsy.jparser.utils.IOUtils;
import spoon.reflect.code.CtConstructorCall;
import spoon.reflect.code.CtFieldRead;
import spoon.reflect.code.CtTypeAccess;
import spoon.reflect.declaration.CtConstructor;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.filter.AbstractFilter;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

public class TestMain {

  private static List<ElementInfo> getElementsByLine(CtType<?> type, List<Integer> lines) {
    if (lines.isEmpty())
      return Collections.emptyList();
    return type.getElements(new AbstractFilter<>() {
      @Override
      public boolean matches(CtElement element) {
        if (!element.getPosition().isValidPosition())
          return false;
        return lines.contains(element.getPosition().getLine());
      }
    }).stream().map(TestMain::getElementInfo).filter(e -> e.getValue() != null).collect(Collectors.toList());
  }

  private static ElementInfo getElementInfo(CtElement element) {
    String type = element.getClass().getSimpleName().replace("Impl", "");
    String value = ElementValueHelper.getValue(element);
    return new ElementInfo(type, value);
  }

  public static void main(String[] args) {
    var gson = IOUtils.createGsonInstance();
    var baseReposPath = "/home/ahmad/workspace/tc-repair/repair-collection/data-clones/temp";
    var baseDataPath = "/home/ahmad/workspace/tc-repair/repair-collection/data-candidates-v2";
    var tests = IOUtils.readCsv("/home/ahmad/workspace/tc-repair/fine-tuning/results/random_sample.csv",
        SampleTest.class);
    var outputTests = new LinkedList<Test>();
    int cnt = 0;
    for (SampleTest t : tests) {
      cnt += 1;
      System.out.println(cnt + ": Test ID start " + t.id);
      var project = t.id.split(":")[0];
      var repoDir = Path.of(baseReposPath, project, "codeMining", "clone");

      var dsJSON = IOUtils.readFile(Path.of(baseDataPath, project, "dataset.json"));
      List<Test> ds = gson.fromJson(dsJSON, new TypeToken<List<Test>>() {
      }.getType());
      var test = ds.stream().filter(d -> d.ID.equals(t.id)).collect(Collectors.toList()).get(0);
      var aCommit = test.aCommit;
      var bCommit = test.bCommit;

      System.out.println("Analyzing code");
      var bWorktreePath = GitAPI.createWorktree(repoDir, bCommit);
      var bSpoon = new Spoon(bWorktreePath.toString(), 11);
      var aWorktreePath = GitAPI.createWorktree(repoDir, aCommit);
      var aSpoon = new Spoon(aWorktreePath.toString(), 11);
      System.out.println("Finished analyzing code");

      test.hunk.sourceElements = getElementsByLine(bSpoon.getTopLevelTypeByFile(test.bPath),
          test.hunk.getSourceLineNumbers());
      test.hunk.targetElements = getElementsByLine(aSpoon.getTopLevelTypeByFile(test.aPath),
          test.hunk.getTargetLineNumbers());
      outputTests.add(test);

      var ogPath = Path.of(baseDataPath, project, "sut_class_changes.json");
      var updatedPath = Path.of(baseDataPath, project, "sut_class_changes_updated.json");
      var classChangesPath = Files.exists(updatedPath) ? updatedPath : ogPath;
      var SUTClassChangesJSON = IOUtils.readFile(classChangesPath);
      List<CommitChanges> SUTClassChanges = gson.fromJson(SUTClassChangesJSON,
          new TypeToken<List<CommitChanges>>() {
          }.getType());
      var commitChanges =
          SUTClassChanges.stream().filter(ch -> ch.getACommit().equals(aCommit)).collect(Collectors.toList());
      if (commitChanges.size() > 1)
        throw new RuntimeException("More than one SUT change found with aCommit " + aCommit);
      var changes = commitChanges.get(0).getChanges();
      for (Change ch : changes) {
        var bType = bSpoon.getTopLevelTypeByFile(ch.getFilePath());
        var aType = aSpoon.getTopLevelTypeByFile(ch.getFilePath());
        for (Hunk h : ch.getHunks()) {
          h.sourceElements = getElementsByLine(bType, h.getSourceLineNumbers());
          if (aType != null)
            h.targetElements = getElementsByLine(aType, h.getTargetLineNumbers());
        }
      }
      IOUtils.saveFile(updatedPath, gson.toJson(SUTClassChanges));
      GitAPI.removeWorktree(repoDir, aCommit);
      GitAPI.removeWorktree(repoDir, bCommit);
    }
    IOUtils.saveFile(Path.of(baseDataPath, "tests.json"), gson.toJson(outputTests));
  }
}
