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


def get_repo(repo):
    clone_dir = Path(Config.get("gh_clones_path")) / repo.replace("/", "@")
    if not clone_dir.exists() or not clone_dir.stat().st_size > 0:
        print(f"Cloning {repo} into {clone_dir}")
        git_repo = git.Repo.clone_from(f"https://github.com/{repo}.git", clone_dir, progress=CloneProgress())
    else:
        git_repo = git.Repo(clone_dir)

    return git_repo


def get_local_diff(tag_pair, repo):
    diff_pair = f"{tag_pair.base.name}...{tag_pair.head.name}"
    diff_cache_file = (
        Path(Config.get("gh_cache_path")) / repo.replace("/", "@") / f"{repo.replace('/', '@')}-{diff_pair}.diff"
    )
    if diff_cache_file.exists() and diff_cache_file.stat().st_size > 0:
        print(f"Read diff from cache at {diff_cache_file}")
        with open(str(diff_cache_file)) as f:
            return f.read()

    git_repo = get_repo(repo)

    print(f"Determining {diff_pair} diff")
    diff = git_repo.git.diff(tag_pair.base.name, tag_pair.head.name)

    diff_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(diff_cache_file), "w") as f:
        f.write(diff)

    return diff


def get_test_file_local(tag, test_path, repo):
    git_repo = get_repo(repo)
    git_repo.git.checkout(tag)

    file_dir = Path(Config.get("gh_clones_path")) / repo.replace("/", "@") / test_path
    with open(file_dir, "r") as file:
        contents = file.read()

    return contents


def get_tags_and_ancestors(repo):
    git_repo = get_repo(repo)

    tags = [t for t in sorted(git_repo.tags, key=lambda x: x.commit.committed_datetime, reverse=True)]
    tag_parents = dict()

    print("Finding tag parents")
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            if git_repo.is_ancestor(tags[j].commit, tags[i].commit):
                tag_parents[tags[i].name] = tags[j].name
                break

        if tags[i].name not in tag_parents:
            tag_parents[tags[i].name] = None

    not_none = sum(value is not None for value in tag_parents.values())
    percent = "%.2f" % (not_none / len(tag_parents) * 100)
    print(f"{percent}% of {len(tag_parents)} tags have valid ancestors")

    return {t.name: t for t in tags}, tag_parents


def copy_tag_code(repo, tag):
    tag_path = Path(Config.get("output_path")) / "tags" / tag.name
    tag_path.mkdir(parents=True, exist_ok=True)
    code_path = tag_path / "code"

    if code_path.exists():
        return code_path

    git_repo = get_repo(repo)
    clone_dir = Path(Config.get("gh_clones_path")) / repo.replace("/", "@")

    git_repo.git.checkout(tag.name, force=True)
    shutil.copytree(str(clone_dir), str(code_path), ignore=shutil.ignore_patterns(".git"))
    return code_path
