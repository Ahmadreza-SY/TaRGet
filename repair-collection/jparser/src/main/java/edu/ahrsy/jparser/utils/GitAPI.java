package edu.ahrsy.jparser.utils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Collections;
import java.util.HashMap;
import java.util.Map;
import java.util.Objects;
import java.util.concurrent.atomic.AtomicInteger;

public class GitAPI {

  private static final Map<String, AtomicInteger> acquiredWorktrees = Collections.synchronizedMap(new HashMap<>());

  public synchronized static void cleanupWorktrees(Path repoDir) {
    var worktreesDir = repoDir.getParent().resolve("commits");
    IOUtils.deleteDir(worktreesDir);
    runCommand(repoDir, "git", "worktree", "prune");
    acquiredWorktrees.clear();
  }

  public static Path createWorktree(Path repoDir, String commit) {
    var acqCnt = acquiredWorktrees.getOrDefault(commit, new AtomicInteger(0));
    acquiredWorktrees.put(commit, acqCnt);
    acqCnt.incrementAndGet();
    var worktreeDir = getWorktreeDir(repoDir, commit);
    if (Files.exists(worktreeDir))
      return worktreeDir;
    runCommand(repoDir, "git", "worktree", "add", worktreeDir.toString(), commit);
    return worktreeDir;
  }

  public static void removeWorktree(Path repoDir, String commit) {
    var acqCnt = acquiredWorktrees.getOrDefault(commit, new AtomicInteger(0));
    if (acqCnt.get() > 1) {
      acqCnt.decrementAndGet();
      return;
    }
    var worktreeDir = getWorktreeDir(repoDir, commit);
    IOUtils.deleteDir(worktreeDir);
    runCommand(repoDir, "git", "worktree", "prune");
    acquiredWorktrees.remove(commit);
  }

  private static Path getWorktreeDir(Path repoDir, String commit) {
    return repoDir.getParent().resolve("commits").resolve(commit).toAbsolutePath();
  }

  private static void runCommand(Path dir, String... command) {
    try {
      Objects.requireNonNull(dir, "directory");
      if (!Files.exists(dir))
        throw new RuntimeException("Can't run command in non-existing directory '" + dir + "'");
      ProcessBuilder pb = new ProcessBuilder().command(command).directory(dir.toFile());
      Process p = pb.start();
      int exit = p.waitFor();
      if (exit != 0)
        throw new AssertionError(String.format("cmd '%s' returned %d", String.join(" ", command), exit));
    } catch (IOException | InterruptedException e) {
      throw new RuntimeException(e);
    }
  }
}
