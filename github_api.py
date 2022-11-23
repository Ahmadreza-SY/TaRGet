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
    diff = diff.encode("utf-8", "replace").decode()

    diff_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(diff_cache_file), "w") as f:
        f.write(diff)
        f.write("\n")

    return diff


def get_test_file_local(tag, test_path, repo):
    git_repo = get_repo(repo)
    git_repo.git.checkout(tag, force=True)

    file_dir = Path(Config.get("gh_clones_path")) / repo.replace("/", "@") / test_path
    with open(file_dir, "rb") as file:
        contents = file.read().decode("unicode-escape").encode("utf-8", "replace").decode()

    return contents


def get_tags_and_ancestors(repo):
    git_repo = get_repo(repo)

    tags = [t for t in sorted(git_repo.tags, key=lambda x: x.commit.committed_datetime, reverse=True)]
    tag_ancestors = []
    tag_children = dict()

    print("Finding tag ancestors")
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            if git_repo.is_ancestor(tags[j].commit, tags[i].commit):
                child = tags[i].name
                ancestor = tags[j].name
                tag_ancestors.append((child, ancestor))

                if ancestor not in tag_children:
                    tag_children[ancestor] = []
                tag_children[ancestor].append(child)

                break

    removed_cnt = 0
    for ancestor, children in tag_children.items():
        if len(children) > 1:
            print(f"WARNING: Ancestor with multiple ({len(children)}) children {ancestor} {children}")
            for child in children[:-1]:
                tag_ancestors.remove((child, ancestor))
                removed_cnt += 1
    print(f"Removed {removed_cnt} tag pairs due to multiple children")


    percent = "%.2f" % (len(tag_ancestors) / (len(tags) -1) * 100)
    print(f"{percent}% of {len(tags) -1} tags have valid ancestors")

    return {t.name: t for t in tags}, tag_ancestors


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
