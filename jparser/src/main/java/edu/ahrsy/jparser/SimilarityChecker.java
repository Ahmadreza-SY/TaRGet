package edu.ahrsy.jparser;

import edu.ahrsy.jparser.spoon.Spoon;
import edu.ahrsy.jparser.utils.IOUtils;
import org.apache.commons.text.similarity.JaroWinklerSimilarity;
import spoon.reflect.declaration.CtExecutable;

public class SimilarityChecker {
  public static final float SIM_THRESHOLD = 0.65f;
  private static final float SIG_SIM_MUL = 1.25f;
  private static final float BODY_SIM_MUL = 1.0f;
  private static final float LINE_SIM_MUL = 0.75f;

  private static Double computeLineSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
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

  private static double computeSignatureSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var sourceSig = Spoon.getSimpleSignature(source);
    var targetSig = Spoon.getSimpleSignature(target);
    return new JaroWinklerSimilarity().apply(sourceSig, targetSig);
  }

  private static double computeBodySimilarity(CtExecutable<?> source, CtExecutable<?> target) {
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

  public static double computeOverallSimilarity(CtExecutable<?> source, CtExecutable<?> target) {
    var lineSimilarity = computeLineSimilarity(source, target);
    var max = SIG_SIM_MUL + BODY_SIM_MUL + (lineSimilarity == null ? 0.0 : LINE_SIM_MUL);
    return (computeSignatureSimilarity(source, target) * SIG_SIM_MUL +
            computeBodySimilarity(source, target) * BODY_SIM_MUL +
            (lineSimilarity == null ? 0.0 : lineSimilarity) * LINE_SIM_MUL) / max;
  }
}
