from pathlib import Path
import json
import requests
import shutil
from tqdm.auto import tqdm
from config import Config
import time
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


accept_diff_header = {"Accept": "application/vnd.github.v3.diff"}
accept_json_header = {"Accept": "application/vnd.github+json"}


def get_token_header():
    return {"Authorization": f'token {Config.get("gh_api_token")}'}


def get(url, headers=None, params=None):
    retry_count = 5
    sleep_sec = 10
    attempts = 0
    while True:
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as err:
            if attempts < retry_count:
                attempts += 1
                print(f"Error: {err}\nRetrying in {sleep_sec} seconds ...")
                time.sleep(sleep_sec)
                continue
            else:
                raise SystemExit(err)


def get_diff(release_pair, repo):
    diff_pair = f"{release_pair.base.tag}...{release_pair.head.tag}"
    diff_cache_file = (
        Path(Config.get("gh_cache_path")) / repo.replace("/", "@") / f"{repo.replace('/', '@')}-{diff_pair}.diff"
    )
    if diff_cache_file.exists() and diff_cache_file.stat().st_size > 0:
        print(f"Read diff from cache at {diff_cache_file}")
        with open(str(diff_cache_file)) as f:
            return f.read()

    print(f"Fetching {diff_pair} diff from GitHub")
    response = get(
        url=f"{Config.get('gh_api_base_url')}/repos/{repo}/compare/{diff_pair}",
        headers={**get_token_header(), **accept_diff_header},
    )

    diff_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(diff_cache_file), "w") as f:
        f.write(response.text)

    return response.text


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


# Using API
# def get_test_file(tag, test_path, repo):
#     response = requests.get(
#         f"{api_base_url}/repos/{repo}/contents/{test_path}",
#         headers={**token_header, **accept_json_header},
#         params={"ref": tag},
#     )
#     file_info = response.json()
#     file_content = base64.b64decode(file_info["content"]).decode("utf-8")
#     return file_content

# Using raw source
def get_test_file(tag, test_path, repo):
    response = get(
        url=f"{Config.get('gh_raw_base_url')}/{repo}/{tag}/{test_path}",
    )
    return response.text


def get_test_file_local(tag, test_path, repo):
    git_repo = get_repo(repo)
    git_repo.git.checkout(tag)

    file_dir = Path(Config.get("gh_clones_path")) / repo.replace("/", "@") / test_path
    with open(file_dir, "r") as file:
        contents = file.read()

    return contents


def get_all_releases(repo):
    releases_cache_file = (
        Path(Config.get("gh_cache_path")) / repo.replace("/", "@") / f"{repo.replace('/', '@')}-releases.json"
    )
    if releases_cache_file.exists() and releases_cache_file.stat().st_size > 0:
        print(f"Read releases from cache at {releases_cache_file}")
        with open(str(releases_cache_file)) as f:
            releases = json.loads(f.read())
            return releases

    page_no = 1
    releases = []
    print("Fetching all releases")
    while True:
        response = get(
            url=f"{Config.get('gh_api_base_url')}/repos/{repo}/releases",
            headers={**get_token_header(), **accept_json_header},
            params={"per_page": 100, "page": page_no},
        ).json()
        if len(response) == 0:
            break
        releases.extend(response)
        page_no += 1
        print(f"Total fetched releases until now: {len(releases)}")

    releases_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(releases_cache_file), "w") as f:
        f.write(json.dumps(releases))
    return releases


def download_file(url, output_file):
    if output_file.exists():
        return

    with requests.get(url, headers={**get_token_header()}, stream=True) as r:
        if r.headers.get("Content-Length") is not None:
            total_length = int(r.headers.get("Content-Length"))
        else:
            total_length = None
        with tqdm.wrapattr(
            r.raw,
            "read",
            total=total_length,
            desc=f"Downloading {output_file.name}",
            ncols=60,
            position=0,
            leave=True,
        ) as raw:
            with open(str(output_file), "wb") as f:
                shutil.copyfileobj(raw, f)


def get_tag_tree(repo, releases):
    git_repo = get_repo(repo)

    tags = [t for t in sorted(git_repo.tags, key=lambda x: x.commit.committed_datetime, reverse=True) if t.name in releases]
    tag_parents = dict()

    print("Finding release parents")
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            if git_repo.is_ancestor(tags[j].commit, tags[i].commit):
                tag_parents[tags[i].name] = tags[j].name
                break

        if tags[i].name not in tag_parents:
            tag_parents[tags[i].name] = None

    for t, p in tag_parents.items():
        print(f"{t}: {p}")

    not_none = sum(value is not None for value in tag_parents.values())
    percent = "%.2f" % (not_none / len(tag_parents) * 100)
    print(f"{percent}% of {len(tag_parents)} tags have valid ancestors")

    return tag_parents


def get_tags_and_ancestors(repo):
    git_repo = get_repo(repo)

    tags = [t for t in sorted(git_repo.tags, key=lambda x: x.commit.committed_datetime, reverse=True)]
    tag_parents = dict()

    print("Finding release parents")
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            if git_repo.is_ancestor(tags[j].commit, tags[i].commit):
                tag_parents[tags[i].name] = tags[j].name
                break

        if tags[i].name not in tag_parents:
            tag_parents[tags[i].name] = None

    for t, p in tag_parents.items():
        print(f"{t}: {p}")

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

    git_repo.git.checkout(tag.name)
    shutil.copytree(str(clone_dir), str(code_path))
    return code_path
