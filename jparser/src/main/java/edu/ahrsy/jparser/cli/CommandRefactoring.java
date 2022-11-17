package edu.ahrsy.jparser.cli;

import com.beust.jcommander.Parameter;
import edu.ahrsy.jparser.refactoringMiner.RefactoringMinerAPI;
import edu.ahrsy.jparser.utils.IOUtils;

import java.nio.file.Path;

public class CommandRefactoring {
  @Parameter(names = {"-r", "--repository-path"},
          description = "Root path of the software Git repository",
          required = true
  )
  public String repoPath;

  @Parameter(names = {"-b", "--base-tag"}, description = "The Git tag of the code before refactor.", required = true)
  public String baseTag;

  @Parameter(names = {"-h", "--head-tag"}, description = "The Git tag of the code after refactor.", required = true)
  public String headTag;

  @Parameter(names = {"-o", "--output-path"}, description = "Output folder for saving refactorings", required = true
  )
  public String outputPath;

  public static void cRefactoring(CommandRefactoring args) {
    var mRefactorings = RefactoringMinerAPI.mineMethodRefactorings(Path.of(args.repoPath), args.baseTag, args.headTag);
    var gson = IOUtils.createGsonInstance();
    var outputJson = gson.toJson(mRefactorings);
    IOUtils.saveFile(Path.of(args.outputPath, "method_refactorings.json"), outputJson);
  }
}
