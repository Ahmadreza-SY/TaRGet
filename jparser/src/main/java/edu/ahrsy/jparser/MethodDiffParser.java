package edu.ahrsy.jparser;

import edu.ahrsy.jparser.entity.MethodChange;
import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import org.apache.commons.text.similarity.JaroWinklerDistance;
import spoon.SpoonException;
import spoon.reflect.declaration.CtExecutable;

import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import java.util.stream.Stream;

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

  public List<MethodChange> detectMethodsChanges(Set<String> changedFiles) {
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

  private List<MethodChange> getCommonMethodsChanges(
          List<CtExecutable<?>> baseMethods, List<CtExecutable<?>> headMethods
  ) {
    var baseMethodsMap = baseMethods.stream().collect(Collectors.toMap(Spoon::getUniqueName, m -> m));
    var methodChanges = new ArrayList<MethodChange>();
    for (var hMethod : headMethods) {
      var hMethodName = Spoon.getUniqueName(hMethod);
      if (!baseMethodsMap.containsKey(hMethodName)) continue;

      var bMethodCode = Spoon.prettyPrintWithoutComments(baseMethodsMap.get(hMethodName));
      var hMethodCode = Spoon.prettyPrintWithoutComments(hMethod);
      if (bMethodCode.equals(hMethodCode)) continue;

      var methodFilePath = Spoon.getRelativePath(hMethod, headSpoon.srcPath);
      var methodChange = new MethodChange(methodFilePath, hMethodName);
      methodChange.extractHunks(bMethodCode, hMethodCode);
      methodChanges.add(methodChange);
    }

    return methodChanges;
  }

  private Double computeLineSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    if (!source.getPosition().isValidPosition() || !target.getPosition().isValidPosition()) {
      System.out.printf("Line similarity: No valid position found for %s or %s%n",
              Spoon.getSimpleName(source),
              Spoon.getSimpleName(target));
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
    var sourceSig = Spoon.getSimpleName(source);
    var targetSig = Spoon.getSimpleName(target);
    return new JaroWinklerDistance().apply(sourceSig, targetSig);
  }

  private double computeBodySimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var sourceBody = source.getBody();
    var targetBody = target.getBody();
    if (sourceBody == null && targetBody == null) return 1.0;
    try {
      return new JaroWinklerDistance().apply(sourceBody == null ? "" : sourceBody.toString(),
              targetBody == null ? "" : targetBody.toString());
    } catch (SpoonException e) {
      System.out.printf("ERROR in computeBodySimilarity: executable = %s or %s%n %s%n",
              source.getSignature(),
              target.getSignature(),
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

  private List<MethodChange> detectMissingMethodsChanges(
          List<CtExecutable<?>> missingMethods, List<CtExecutable<?>> newMethods
  ) {
    var methodChanges = new ArrayList<MethodChange>();

    // If no new methods are added, the missing method is deleted
    if (newMethods.isEmpty()) {
      for (var missingMethod : missingMethods) {
        var methodFilePath = Spoon.getRelativePath(missingMethod, baseSpoon.srcPath);
        var methodChange = new MethodChange(methodFilePath, Spoon.getUniqueName(missingMethod));
        methodChange.extractHunks(Spoon.prettyPrintWithoutComments(missingMethod), "");
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

      var methodChange = new MethodChange(missingMethodFile, Spoon.getUniqueName(missingMethod));
      // If the most similar method has higher similarity than the threshold, it's matched
      if (maxSimilarity > SIM_THRESHOLD) {
        methodChange.extractHunks(Spoon.prettyPrintWithoutComments(missingMethod),
                Spoon.prettyPrintWithoutComments(mostSimilarMethod));
      }
      // Otherwise, the missing method is deleted
      else {
        methodChange.extractHunks(Spoon.prettyPrintWithoutComments(missingMethod), "");
      }
      methodChanges.add(methodChange);
    }

    return methodChanges;
  }
}
