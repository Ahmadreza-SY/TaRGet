package edu.ahrsy.jparser;

import gr.uom.java.xmi.CompositeType;
import gr.uom.java.xmi.LeafType;
import gr.uom.java.xmi.UMLOperation;
import gr.uom.java.xmi.UMLType;
import gr.uom.java.xmi.diff.ExtractOperationRefactoring;
import org.eclipse.jgit.lib.Repository;
import org.refactoringminer.api.*;
import org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl;
import org.refactoringminer.util.GitServiceImpl;

import java.io.File;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.stream.Collectors;

public class RefactoringMiner {
  public static ArrayList<RefactoringType> methodRefactoringTypes = new ArrayList<>(Arrays.asList(RefactoringType.EXTRACT_OPERATION,
          RefactoringType.RENAME_METHOD,
          RefactoringType.INLINE_OPERATION,
          RefactoringType.MOVE_OPERATION,
          RefactoringType.MOVE_AND_RENAME_OPERATION,
          RefactoringType.PULL_UP_OPERATION,
          RefactoringType.PUSH_DOWN_OPERATION,
          RefactoringType.EXTRACT_AND_MOVE_OPERATION,
          RefactoringType.MOVE_AND_INLINE_OPERATION,
          RefactoringType.EXTRACT_VARIABLE,
          RefactoringType.INLINE_VARIABLE,
          RefactoringType.RENAME_VARIABLE,
          RefactoringType.RENAME_PARAMETER,
          RefactoringType.MERGE_VARIABLE,
          RefactoringType.MERGE_PARAMETER,
          RefactoringType.SPLIT_VARIABLE,
          RefactoringType.SPLIT_PARAMETER,
          RefactoringType.REPLACE_VARIABLE_WITH_ATTRIBUTE,
          RefactoringType.REPLACE_ATTRIBUTE_WITH_VARIABLE,
          RefactoringType.PARAMETERIZE_VARIABLE,
          RefactoringType.LOCALIZE_PARAMETER,
          RefactoringType.PARAMETERIZE_ATTRIBUTE,
          RefactoringType.CHANGE_RETURN_TYPE,
          RefactoringType.CHANGE_VARIABLE_TYPE,
          RefactoringType.CHANGE_PARAMETER_TYPE,
          RefactoringType.ADD_METHOD_ANNOTATION,
          RefactoringType.REMOVE_METHOD_ANNOTATION,
          RefactoringType.MODIFY_METHOD_ANNOTATION,
          RefactoringType.ADD_PARAMETER_ANNOTATION,
          RefactoringType.REMOVE_PARAMETER_ANNOTATION,
          RefactoringType.MODIFY_PARAMETER_ANNOTATION,
          RefactoringType.ADD_PARAMETER,
          RefactoringType.REMOVE_PARAMETER,
          RefactoringType.REORDER_PARAMETER,
          RefactoringType.ADD_VARIABLE_ANNOTATION,
          RefactoringType.REMOVE_VARIABLE_ANNOTATION,
          RefactoringType.MODIFY_VARIABLE_ANNOTATION,
          RefactoringType.ADD_THROWN_EXCEPTION_TYPE,
          RefactoringType.REMOVE_THROWN_EXCEPTION_TYPE,
          RefactoringType.CHANGE_THROWN_EXCEPTION_TYPE,
          RefactoringType.CHANGE_OPERATION_ACCESS_MODIFIER,
          RefactoringType.ADD_METHOD_MODIFIER,
          RefactoringType.REMOVE_METHOD_MODIFIER,
          RefactoringType.ADD_VARIABLE_MODIFIER,
          RefactoringType.ADD_PARAMETER_MODIFIER,
          RefactoringType.REMOVE_VARIABLE_MODIFIER,
          RefactoringType.REMOVE_PARAMETER_MODIFIER,
          RefactoringType.REPLACE_LOOP_WITH_PIPELINE,
          RefactoringType.REPLACE_PIPELINE_WITH_LOOP,
          RefactoringType.REPLACE_ANONYMOUS_WITH_LAMBDA));


  private static String generateMethodSignature(UMLOperation operation) {
    String className = operation.getClassName();
    String name = operation.getName();
    List<String> parameterTypes = operation.getParameterTypeList()
            .stream()
            .map(UMLType::extractTypeObject)
            .collect(Collectors.toList());

    return String.format("%s.%s(%s)", className, name, String.join(",", parameterTypes));
  }

  // TODO class type is not fully qualified
  private static String getClassType(UMLType type) {
    if (type instanceof LeafType) return type.getClassType();
    else if (type instanceof CompositeType) return ((CompositeType) type).getLeftType().getClassType();
    else return type.toQualifiedString();
  }

  public static String getRefactoredMethodSignature(Refactoring refactoring) {
//  Format:  org.jkiss.dbeaver.parser.common.GrammarAnalyzer.discoverPathsFrom(java.util.Map,org.jkiss.dbeaver.parser.common.grammar.nfa.GrammarNfaTransition)
    switch (refactoring.getRefactoringType()) {
      case EXTRACT_OPERATION:
        var _refactoring = (ExtractOperationRefactoring) refactoring;
        return generateMethodSignature((UMLOperation) _refactoring.getSourceOperationBeforeExtraction());
      default:
        return null;
    }
  }

  public static void main(String[] args) {
    try {
      PrintStream o = new PrintStream(new File("log.txt"));
      System.setOut(o);
      GitService gitService = new GitServiceImpl();
      Repository repo = gitService.openRepository(
              "/home/ahmadreza/Workspace/PhD/tc-repair/api_cache/clones/apache@shardingsphere");
      GitHistoryRefactoringMiner miner = new GitHistoryRefactoringMinerImpl();

//      miner.detectBetweenTags(repo, "5.1.1", "5.1.2", new RefactoringHandler() {
      miner.detectAtCommit(repo, "10fdd38cbfd1b98be5009dfad89933dd572bcd88", new RefactoringHandler() {
        @Override
        public void handleException(String commitId, Exception e) {
        }

        @Override
        public void handle(String commitId, List<Refactoring> refactorings) {
          var methodRefactoring = refactorings.stream()
                  .filter(r -> methodRefactoringTypes.contains(r.getRefactoringType()))
                  .collect(Collectors.toList());
          if (!methodRefactoring.isEmpty())
            System.out.println("************ Refactorings at commit " + commitId + " ************");
          for (Refactoring refactoring : methodRefactoring) {
            System.out.println("*REF* " + refactoring);
            System.out.println("*SIG* " + getRefactoredMethodSignature(refactoring));
            System.out.println();
          }
        }
      });
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }
}
