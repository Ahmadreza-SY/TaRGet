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


def get_working_path():
    repo_path = Config.get("repo_path")
    if repo_path is not None:
        return repo_path
    return Config.get("output_path")


def get_repo(repo_name):
    output_path = get_working_path()
    clone_dir = Path(output_path) / "codeMining" / "clone"
    if not clone_dir.exists() or not clone_dir.stat().st_size > 0:
        print(f"Cloning {repo_name} into {clone_dir}")
        git_repo = git.Repo.clone_from(f"https://github.com/{repo_name}.git", clone_dir, progress=CloneProgress())
    else:
        git_repo = git.Repo(clone_dir)

    return git_repo


def cleanup_worktrees(repo_name):
    output_path = get_working_path()
    worktrees_path = Path(output_path) / "codeMining" / "commits"
    shutil.rmtree(str(worktrees_path), ignore_errors=True)
    repo = get_repo(repo_name)
    repo.git.worktree("prune")


def copy_commit_code(repo_name, commit, id):
    output_path = get_working_path()
    base_path = Path(output_path) / "codeMining" / "commits"
    copy_path = base_path / f"{commit}-{id}"
    if copy_path.exists():
        return copy_path

    repo = get_repo(repo_name)
    repo.git.worktree("add", str(copy_path.absolute()), commit)
    return copy_path


def remove_commit_code(repo_name, code_path):
    shutil.rmtree(str(code_path), ignore_errors=True)
    repo = get_repo(repo_name)
    repo.git.worktree("prune")


def get_all_commits(repo_name):
    repo = get_repo(repo_name)
    repo.git.checkout("origin/HEAD", force=True)
    commits = []
    unique_shas = set()
    for commit in repo.iter_commits():
        if len(commit.parents) > 1:
            continue
        if commit.hexsha in unique_shas:
            continue
        unique_shas.add(commit.hexsha)
        commits.append(commit)
    print(f"Found {len(commits)} commits")
    return commits


def get_file_versions(file_diff, commit, repo_name):
    before = get_file_version(commit.parents[0].hexsha, file_diff.b_path, repo_name)
    after = get_file_version(commit.hexsha, file_diff.a_path, repo_name)
    return before, after


def get_file_version(commit_hex, file_path, repo_name):
    repo = get_repo(repo_name)
    return repo.git.show(f"{commit_hex}:{file_path}")


def get_short_commit(commit, repo_name):
    repo = get_repo(repo_name)
    return repo.git.rev_parse(commit.hexsha, short=True)


def get_commit_time(commit, repo_name):
    repo = get_repo(repo_name)
    return repo.commit(commit).committed_date


def get_commit(commit_sha, repo_name):
    repo = get_repo(repo_name)
    return repo.commit(commit_sha)
