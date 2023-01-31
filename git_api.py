from pathlib import Path
import shutil
from tqdm.auto import tqdm
from config import Config
import git
from git import RemoteProgress


class CloneProgress(RemoteProgress):
    def __init__(self):
        super().__init__()
        self.pbar = tqdm()

    def update(self, op_code, cur_count, max_count=None, message=""):
        self.pbar.total = max_count
        self.pbar.n = cur_count
        self.pbar.refresh()


def get_repo(repo, output_path=Config.get("output_path")):
    clone_dir = Path(output_path) / "clone"
    if not clone_dir.exists() or not clone_dir.stat().st_size > 0:
        print(f"Cloning {repo} into {clone_dir}")
        git_repo = git.Repo.clone_from(f"https://github.com/{repo}.git", clone_dir, progress=CloneProgress())
    else:
        git_repo = git.Repo(clone_dir)

    return git_repo


def cleanup_worktrees(repo_name, output_path=Config.get("output_path"), git_path=None):
    worktrees_path = Path(output_path) / "commits"
    shutil.rmtree(str(worktrees_path), ignore_errors=True)
    repo = get_repo(repo_name, output_path if not git_path else git_path)
    repo.git.worktree("prune")


def copy_commit_code(repo_name, commit, output_path=Config.get("output_path"), git_path=None):
    copy_path = output_path / "commits" / commit
    if copy_path.exists():
        return copy_path

    repo = get_repo(repo_name, output_path if not git_path else git_path)
    repo.git.worktree("add", str(copy_path.absolute()), commit)
    return copy_path


def remove_commit_code(repo_name, commit):
    code_path = Path(Config.get("output_path")) / "commits" / commit
    shutil.rmtree(str(code_path), ignore_errors=True)
    repo = get_repo(repo_name)
    repo.git.worktree("prune")


def get_all_commits(repo_name):
    repo = get_repo(repo_name)
    repo.git.checkout("origin/HEAD", force=True)
    return list(repo.iter_commits())


def get_file_versions(file_diff, commit, repo_name):
    repo = get_repo(repo_name)
    before = repo.git.show(f"{commit.parents[0].hexsha}:{file_diff.b_path}")
    after = repo.git.show(f"{commit.hexsha}:{file_diff.a_path}")
    return before, after


def get_short_commit(commit, repo_name):
    repo = get_repo(repo_name)
    return repo.git.rev_parse(commit.hexsha, short=True)


def get_commit_time(commit, repo_name):
    repo = get_repo(repo_name)
    return repo.commit(commit).committed_date


def get_commit(commit_sha, repo_name):
    repo = get_repo(repo_name)
    return repo.commit(commit_sha)
