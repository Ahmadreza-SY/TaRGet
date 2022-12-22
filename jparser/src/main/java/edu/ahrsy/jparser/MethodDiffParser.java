package edu.ahrsy.jparser;

import edu.ahrsy.jparser.entity.Change;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import org.apache.commons.text.similarity.JaroWinklerSimilarity;
import spoon.reflect.declaration.CtExecutable;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

// TODO Remove
public class MethodDiffParser {
  private static final float SIM_THRESHOLD = 0.65f;
  private static final float SIG_SIM_MUL = 1.25f;
  private static final float BODY_SIM_MUL = 1.0f;
  private static final float LINE_SIM_MUL = 0.75f;
  private final Spoon baseSpoon;
  private final Spoon headSpoon;

  public MethodDiffParser(String baseSrcPath, String headSrcPath, Integer complianceLevel) {
    this.baseSpoon = new Spoon(baseSrcPath, complianceLevel);
    this.headSpoon = new Spoon(headSrcPath, complianceLevel);
  }

  public List<Change> detectMethodsChanges(Set<String> changedFiles) {
    var baseMethods = baseSpoon.getExecutablesByFile(changedFiles);
    var headMethods = headSpoon.getExecutablesByFile(changedFiles);

    var commonMethodsChanges = getCommonMethodsChanges(baseMethods, headMethods);

    var baseMethodNames = baseMethods.stream().map(Spoon::getUniqueName).collect(Collectors.toSet());
    var headMethodNames = headMethods.stream().map(Spoon::getUniqueName).collect(Collectors.toSet());
    var missingMethods = baseMethods.stream()
            .filter(bm -> !headMethodNames.contains(Spoon.getUniqueName(bm)))
            .collect(Collectors.toList());
    var newMethods = headMethods.stream()
            .filter(hm -> !baseMethodNames.contains(Spoon.getUniqueName(hm)))
            .collect(Collectors.toList());
    var missingMethodsChanges = detectMissingMethodsChanges(missingMethods, newMethods);

    return Stream.concat(commonMethodsChanges.stream(), missingMethodsChanges.stream()).collect(Collectors.toList());
  }

  private List<Change> getCommonMethodsChanges(
          List<CtExecutable<?>> baseMethods, List<CtExecutable<?>> headMethods
  ) {
    var baseMethodsMap = baseMethods.stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m, (m1, m2) -> {
      System.out.printf("Duplicate key found: %s ; %s%n", m1.getSignature(), m2.getSignature());
      return m1;
    }));
    var methodChanges = new ArrayList<Change>();
    for (var hMethod : headMethods) {
      var hMethodName = Spoon.getUniqueName(hMethod);
      if (!baseMethodsMap.containsKey(hMethodName)) continue;

      var bMethodCode = Spoon.prettyPrint(baseMethodsMap.get(hMethodName));
      var hMethodCode = Spoon.prettyPrint(hMethod);
      if (bMethodCode.equals(hMethodCode)) continue;

      var methodFilePath = Spoon.getRelativePath(hMethod, headSpoon.srcPath);
      var methodChange = new Change(methodFilePath, hMethodName);
      methodChange.extractHunks(bMethodCode, hMethodCode);
      methodChanges.add(methodChange);
    }

    return methodChanges;
  }

  private Double computeLineSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    if (!source.getPosition().isValidPosition() || !target.getPosition().isValidPosition()) {
      /*System.out.printf("Line similarity: No valid position found for %s or %s%n",
              Spoon.getSimpleSignature(source),
              Spoon.getSimpleSignature(target));*/
      return null;
    }
    var sourceLineCnt = IOUtils.countLines(source.getPosition().getCompilationUnit().getFile());
    var targetLineCnt = IOUtils.countLines(target.getPosition().getCompilationUnit().getFile());
    double maxLineCnt = Integer.max(sourceLineCnt, targetLineCnt);

    var sourceLine = source.getPosition().getLine();
    var targetLine = target.getPosition().getLine();
    double lineDistance = Math.abs(sourceLine - targetLine);
    return (maxLineCnt - lineDistance) / maxLineCnt;
  }

  private double computeSignatureSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var sourceSig = Spoon.getSimpleSignature(source);
    var targetSig = Spoon.getSimpleSignature(target);
    return new JaroWinklerSimilarity().apply(sourceSig, targetSig);
  }

  private double computeBodySimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var sourceBody = source.getBody();
    var targetBody = target.getBody();
    if (sourceBody == null && targetBody == null) return 1.0;
    try {
      return new JaroWinklerSimilarity().apply(sourceBody == null ? "" : sourceBody.toString(),
              targetBody == null ? "" : targetBody.toString());
    } catch (Exception e) {
      System.out.printf("ERROR in computeBodySimilarity: executable = %s or %s%n %s%n",
              Spoon.getSimpleSignature(source),
              Spoon.getSimpleSignature(target),
              e.getMessage());
    }
    return computeSignatureSimilarity(source, target);
  }

  private double computeOverallSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var lineSimilarity = computeLineSimilarity(source, target);
    var max = SIG_SIM_MUL + BODY_SIM_MUL + (lineSimilarity == null ? 0.0 : LINE_SIM_MUL);
    return (computeSignatureSimilarity(source, target) * SIG_SIM_MUL +
            computeBodySimilarity(source, target) * BODY_SIM_MUL +
            (lineSimilarity == null ? 0.0 : lineSimilarity) * LINE_SIM_MUL) / max;
  }

  private List<Change> detectMissingMethodsChanges(
          List<CtExecutable<?>> missingMethods, List<CtExecutable<?>> newMethods
  ) {
    var methodChanges = new ArrayList<Change>();

    // If no new methods are added, the missing method is deleted
    if (newMethods.isEmpty()) {
      for (var missingMethod : missingMethods) {
        var methodFilePath = Spoon.getRelativePath(missingMethod, baseSpoon.srcPath);
        var methodChange = new Change(methodFilePath, Spoon.getUniqueName(missingMethod));
        methodChange.extractHunks(Spoon.prettyPrint(missingMethod), "");
        methodChanges.add(methodChange);
      }
      return methodChanges;
    }

    for (var missingMethod : missingMethods) {
      var missingMethodFile = Spoon.getRelativePath(missingMethod, baseSpoon.srcPath);
      CtExecutable<?> mostSimilarMethod = null;
      double maxSimilarity = -1;
      for (var newMethod : newMethods) {
        var newMethodFile = Spoon.getRelativePath(newMethod, headSpoon.srcPath);
        // missing method and new method should be in the same file
        if (!missingMethodFile.equals(newMethodFile)) continue;
        // missing method and new method should be both the same type (constructors or methods)
        if (missingMethod.getClass() != newMethod.getClass()) continue;

        var similarity = computeOverallSimilarity(missingMethod, newMethod);
        if (similarity > maxSimilarity) {
          mostSimilarMethod = newMethod;
          maxSimilarity = similarity;
        }
      }

      var methodChange = new Change(missingMethodFile, Spoon.getUniqueName(missingMethod));
      // If the most similar method has higher similarity than the threshold, it's matched
      if (maxSimilarity > SIM_THRESHOLD) {
        methodChange.extractHunks(Spoon.prettyPrint(missingMethod), Spoon.prettyPrint(mostSimilarMethod));
      }
      // Otherwise, the missing method is deleted
      else {
        methodChange.extractHunks(Spoon.prettyPrint(missingMethod), "");
      }
      methodChanges.add(methodChange);
    }

    return methodChanges;
  }
}
