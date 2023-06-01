package edu.ahrsy.jparser.refactoringminer;

import gr.uom.java.xmi.UMLOperation;
import gr.uom.java.xmi.UMLType;
import gr.uom.java.xmi.VariableDeclarationContainer;
import gr.uom.java.xmi.diff.*;
import org.refactoringminer.api.*;
import org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl;
import org.refactoringminer.util.GitServiceImpl;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.spi.LocationAwareLogger;

import java.lang.reflect.Field;
import java.nio.file.Path;
import java.util.*;
import java.util.stream.Collectors;

public class RefactoringMinerAPI {
  private static String getMethodSignature(UMLOperation operation) {
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

  public static Map<String, List<RefactoringType>> mineMethodRefactorings(String beforePath, String afterPath) {
    var methodRefactorings = new HashMap<String, List<RefactoringType>>();
    try {
      GitHistoryRefactoringMiner miner = new GitHistoryRefactoringMinerImpl();

      Path before = Path.of(beforePath).toAbsolutePath();
      Path after = Path.of(afterPath).toAbsolutePath();
      miner.detectAtDirectories(before, after, new RefactoringHandler() {
        @Override
        public void handle(String commitId, List<Refactoring> refactorings) {
          for (Refactoring refactoring : refactorings) {
            VariableDeclarationContainer container = getRefactorContainer(refactoring);
            if (!(container instanceof UMLOperation)) continue;
            String mSignature = getMethodSignature((UMLOperation) container);
            if (mSignature == null) continue;
            if (!methodRefactorings.containsKey(mSignature))
              methodRefactorings.put(mSignature, new ArrayList<>());
            methodRefactorings.get(mSignature).add(refactoring.getRefactoringType());
          }
        }
      });
    } catch (Exception e) {
      throw new RuntimeException(e);
    }
    return methodRefactorings;
  }

  private static RenameRefactoring createRenameRefactoring(Refactoring refactoring) {
    var refType = refactoring.getRefactoringType();
    String originalName, newName;
    switch (refType) {
      case RENAME_CLASS: {
        var _refactoring = (RenameClassRefactoring) refactoring;
        originalName = _refactoring.getOriginalClassName();
        newName = _refactoring.getRenamedClassName();
        break;
      }
      case MOVE_RENAME_CLASS: {
        var _refactoring = (MoveAndRenameClassRefactoring) refactoring;
        originalName = _refactoring.getOriginalClassName();
        newName = _refactoring.getRenamedClassName();
        break;
      }
      case RENAME_METHOD: {
        var _refactoring = (RenameOperationRefactoring) refactoring;
        originalName = getMethodSignature(_refactoring.getOriginalOperation());
        newName = getMethodSignature(_refactoring.getRenamedOperation());
        break;
      }
      default:
        throw new RuntimeException("Not rename refactoring " + refType);
    }

    return new RenameRefactoring(refType.toString(), originalName, newName);
  }

  public static List<RenameRefactoring> mineRenameRefactorings(String commit, String projectPath) {
    var renameTypes = EnumSet.of(RefactoringType.RENAME_CLASS, RefactoringType.RENAME_METHOD,
        RefactoringType.MOVE_RENAME_CLASS);
    var renameRefactorings = new ArrayList<RenameRefactoring>();

    try {
      var miner = new GitHistoryRefactoringMinerImpl();
      var gitService = new GitServiceImpl();
      var repo = gitService.cloneIfNotExists(projectPath, null);
      disableLogs();

      miner.detectAtCommit(repo, commit, new RefactoringHandler() {
        @Override
        public void handle(String commitId, List<Refactoring> refactorings) {
          for (Refactoring refactoring : refactorings) {
            var refType = refactoring.getRefactoringType();
            if (!renameTypes.contains(refType))
              continue;
            renameRefactorings.add(createRenameRefactoring(refactoring));
          }
        }
      });
    } catch (Exception e) {
      throw new RuntimeException(e);
    }

    return renameRefactorings;
  }

  private static void disableLogs() {
    try {
      Logger l = LoggerFactory.getLogger("org.refactoringminer.rm1.GitHistoryRefactoringMinerImpl");
      Field f = l.getClass().getDeclaredField("currentLogLevel");
      f.setAccessible(true);
      f.set(l, LocationAwareLogger.WARN_INT);
    } catch (NoSuchFieldException | IllegalAccessException e) {
      throw new RuntimeException(e);
    }
  }
}