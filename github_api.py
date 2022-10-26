from pathlib import Path
import json
import requests
import shutil
from tqdm.auto import tqdm
from config import Config
import time
import git

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


def get_tag_tree(repo):
    clone_dir = (
            Path(Config.get("gh_clones_path"))
            / repo.replace("/", "@")
    )
    if not clone_dir.exists() or not clone_dir.stat().st_size > 0:
        print(f"Cloning {repo} into {clone_dir}")
        git_repo = git.Repo.clone_from(f"https://github.com/{repo}.git", clone_dir)
    else:
        git_repo = git.Repo(clone_dir)

    tags = [t for t in sorted(git_repo.tags, key=lambda x: x.commit.committed_datetime, reverse=True)]
    tag_parents = dict()
    commit_parents = {t.commit.hexsha: t for t in tags}
    commit_queue = sorted([t.commit for t in tags], key=lambda x: x.committed_datetime, reverse=True)

    print("Finding release parents")
    while len(commit_queue) > 0:
        curr_commit = commit_queue.pop(0)

        for p in curr_commit.parents:
            if p.hexsha not in commit_parents:
                commit_parents[p.hexsha] = commit_parents[curr_commit.hexsha]
                insert_index = next((i for i, c in enumerate(commit_queue) if c.committed_datetime < p.committed_datetime), -1)
                commit_queue.insert(insert_index, p)

            elif commit_parents[p.hexsha].name != commit_parents[curr_commit.hexsha].name:
                # If the current commit has a tag that already has an assigned parent tag
                # And the current commit's tag's parent tag happened before the current parent commit's parent tag
                # And the current commit is later than the parent commit's parent tag
                # And the current commit's parent tag is later than the parent commit
                if commit_parents[curr_commit.hexsha].name in tag_parents and \
                        tag_parents[commit_parents[curr_commit.hexsha].name].commit.committed_datetime < commit_parents[p.hexsha].commit.committed_datetime < curr_commit.committed_datetime and \
                        commit_parents[curr_commit.hexsha].commit.committed_datetime > p.committed_datetime:
                    tag_parents[commit_parents[curr_commit.hexsha].name] = commit_parents[p.hexsha]

                if commit_parents[p.hexsha].commit.committed_datetime < commit_parents[curr_commit.hexsha].commit.committed_datetime:
                    if commit_parents[curr_commit.hexsha].name not in tag_parents:
                        tag_parents[commit_parents[curr_commit.hexsha].name] = commit_parents[p.hexsha]

                else:
                    if commit_parents[p.hexsha].name not in tag_parents:
                        tag_parents[commit_parents[p.hexsha].name] = commit_parents[curr_commit.hexsha]

                    commit_parents[p.hexsha] = commit_parents[curr_commit.hexsha]

    tag_parents = {t:p.name for t, p in tag_parents.items()}
    for t, p in tag_parents.items():
        print(f"{t}: {p}")

    return tag_parents


get_tag_tree("alibaba/fastjson")