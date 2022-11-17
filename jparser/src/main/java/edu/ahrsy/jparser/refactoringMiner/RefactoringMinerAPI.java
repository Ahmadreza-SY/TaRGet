package edu.ahrsy.jparser.refactoringMiner;

import gr.uom.java.xmi.UMLOperation;
import gr.uom.java.xmi.UMLType;
import gr.uom.java.xmi.VariableDeclarationContainer;
import gr.uom.java.xmi.diff.*;
import org.apache.commons.lang3.exception.ExceptionUtils;
import org.eclipse.jgit.lib.Repository;
import org.refactoringminer.api.GitHistoryRefactoringMiner;
import org.refactoringminer.api.GitService;
import org.refactoringminer.api.Refactoring;
import org.refactoringminer.api.RefactoringHandler;
import org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl;
import org.refactoringminer.util.GitServiceImpl;
import org.slf4j.LoggerFactory;

import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class RefactoringMinerAPI {
  private static String generateMethodSignature(UMLOperation operation) {
    String className = operation.getClassName();
    String name = operation.getName();
    List<String> parameterTypes = operation.getParameterTypeList()
            .stream()
            .map(UMLType::getClassType)
            .collect(Collectors.toList());

    return String.format("%s.%s(%s)", className, name, String.join(",", parameterTypes));
  }

  private static VariableDeclarationContainer getRefactorContainer(Refactoring refactoring) {
    switch (refactoring.getRefactoringType()) {
      case EXTRACT_OPERATION:
      case EXTRACT_AND_MOVE_OPERATION: {
        var _refactoring = (ExtractOperationRefactoring) refactoring;
        return _refactoring.getSourceOperationBeforeExtraction();
      }
      case RENAME_METHOD: {
        var _refactoring = (RenameOperationRefactoring) refactoring;
        return _refactoring.getOriginalOperation();
      }
      case INLINE_OPERATION:
      case MOVE_AND_INLINE_OPERATION: {
        var _refactoring = (InlineOperationRefactoring) refactoring;
        return _refactoring.getInlinedOperation();
      }
      case MOVE_OPERATION:
      case MOVE_AND_RENAME_OPERATION:
      case PULL_UP_OPERATION:
      case PUSH_DOWN_OPERATION: {
        var _refactoring = (MoveOperationRefactoring) refactoring;
        return _refactoring.getOriginalOperation();
      }
      case EXTRACT_VARIABLE: {
        var _refactoring = (ExtractVariableRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case INLINE_VARIABLE: {
        var _refactoring = (InlineVariableRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case RENAME_VARIABLE:
      case RENAME_PARAMETER:
      case PARAMETERIZE_ATTRIBUTE:
      case PARAMETERIZE_VARIABLE:
      case REPLACE_VARIABLE_WITH_ATTRIBUTE:
      case REPLACE_ATTRIBUTE_WITH_VARIABLE:
      case LOCALIZE_PARAMETER: {
        var _refactoring = (RenameVariableRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case MERGE_VARIABLE:
      case MERGE_PARAMETER: {
        var _refactoring = (MergeVariableRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case SPLIT_VARIABLE:
      case SPLIT_PARAMETER: {
        var _refactoring = (SplitVariableRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case CHANGE_RETURN_TYPE: {
        var _refactoring = (ChangeReturnTypeRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case CHANGE_VARIABLE_TYPE:
      case CHANGE_PARAMETER_TYPE: {
        var _refactoring = (ChangeVariableTypeRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_METHOD_ANNOTATION: {
        var _refactoring = (AddMethodAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_METHOD_ANNOTATION: {
        var _refactoring = (RemoveMethodAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case MODIFY_METHOD_ANNOTATION: {
        var _refactoring = (ModifyMethodAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_PARAMETER_ANNOTATION:
      case ADD_VARIABLE_ANNOTATION: {
        var _refactoring = (AddVariableAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_PARAMETER_ANNOTATION:
      case REMOVE_VARIABLE_ANNOTATION: {
        var _refactoring = (RemoveVariableAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case MODIFY_PARAMETER_ANNOTATION:
      case MODIFY_VARIABLE_ANNOTATION: {
        var _refactoring = (ModifyVariableAnnotationRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_PARAMETER: {
        var _refactoring = (AddParameterRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_PARAMETER: {
        var _refactoring = (RemoveParameterRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REORDER_PARAMETER: {
        var _refactoring = (ReorderParameterRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_THROWN_EXCEPTION_TYPE: {
        var _refactoring = (AddThrownExceptionTypeRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_THROWN_EXCEPTION_TYPE: {
        var _refactoring = (RemoveThrownExceptionTypeRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case CHANGE_THROWN_EXCEPTION_TYPE: {
        var _refactoring = (ChangeThrownExceptionTypeRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case CHANGE_OPERATION_ACCESS_MODIFIER: {
        var _refactoring = (ChangeOperationAccessModifierRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_METHOD_MODIFIER: {
        var _refactoring = (AddMethodModifierRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_METHOD_MODIFIER: {
        var _refactoring = (RemoveMethodModifierRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case ADD_VARIABLE_MODIFIER:
      case ADD_PARAMETER_MODIFIER: {
        var _refactoring = (AddVariableModifierRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REMOVE_VARIABLE_MODIFIER:
      case REMOVE_PARAMETER_MODIFIER: {
        var _refactoring = (RemoveVariableModifierRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REPLACE_LOOP_WITH_PIPELINE: {
        var _refactoring = (ReplaceLoopWithPipelineRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REPLACE_PIPELINE_WITH_LOOP: {
        var _refactoring = (ReplacePipelineWithLoopRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      case REPLACE_ANONYMOUS_WITH_LAMBDA: {
        var _refactoring = (ReplaceAnonymousWithLambdaRefactoring) refactoring;
        return _refactoring.getOperationBefore();
      }
      default:
        return null;
    }
  }

  public static List<MethodRefactoring> mineMethodRefactorings(Path repoPath, String baseTag, String headTag) {
    var errLogger = LoggerFactory.getLogger("RefMinerErrors");
    try {
      GitService gitService = new GitServiceImpl();
      Repository repo = gitService.openRepository(repoPath.toString());
      GitHistoryRefactoringMiner miner = new GitHistoryRefactoringMinerImpl();

      Map<String, MethodRefactoring> mRefactorings = new HashMap<>();
      miner.detectBetweenTags(repo, baseTag, headTag, new RefactoringHandler() {
        @Override
        public void handleException(String commitId, Exception e) {
          var repoName = repo.getConfig().getString("remote", "origin", "url");
          errLogger.warn("#Error " + e.getClass().getName() + " repo " + repoName + " at commit " + commitId);
          errLogger.warn("Stacktrace:\n" + ExceptionUtils.getStackTrace(e));
        }

        @Override
        public void handle(String commitId, List<Refactoring> refactorings) {
          for (Refactoring refactoring : refactorings) {
            VariableDeclarationContainer container = getRefactorContainer(refactoring);
            if (!(container instanceof UMLOperation)) continue;
            String mSignature = generateMethodSignature((UMLOperation) container);
            if (mSignature == null) continue;
            if (!mRefactorings.containsKey(mSignature))
              mRefactorings.put(mSignature, new MethodRefactoring(mSignature));
            mRefactorings.get(mSignature).addRefactoring(commitId, refactoring.getRefactoringType());
          }
        }
      });
      return new ArrayList<>(mRefactorings.values());
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
  }
}
