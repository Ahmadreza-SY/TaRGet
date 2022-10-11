import requests
from pathlib import Path
import json
import requests
import shutil
from tqdm.auto import tqdm
from config import Config
import time
from datetime import datetime

accept_diff_header = {"Accept": "application/vnd.github.v3.diff"}
accept_json_header = {"Accept": "application/vnd.github+json"}


def get_token_header():
    return {"Authorization": f'token {Config.get("gh_api_token")}'}


def get(url, headers=None, params=None):
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response
    except requests.exceptions.HTTPError as err:
        raise SystemExit(err)


def get_diff(release_pair, repo):
    diff_pair = f"{release_pair.base.tag}...{release_pair.head.tag}"
    diff_cache_file = (
        Path(Config.get("gh_cache_path"))
        / repo.replace("/", "@")
        / f"{repo.replace('/', '@')}-{diff_pair}.diff"
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
        Path(Config.get("gh_cache_path"))
        / repo.replace("/", "@")
        / f"{repo.replace('/', '@')}-releases.json"
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


def get_release_tree(repo="apache/dubbo", releases=None):
    tags_cache_file = (
        Path(Config.get("gh_cache_path"))
        / repo.replace("/", "@")
        / f"{repo.replace('/', '@')}-tags.json"
    )
    if tags_cache_file.exists() and tags_cache_file.stat().st_size > 0:
        print(f"Read tags from cache at {tags_cache_file}")
        with open(str(tags_cache_file)) as f:
            tags = json.loads(f.read())

    else:
        page_no = 1
        tags = []
        while True:
            response = get(
                url=f"{Config.get('gh_api_base_url')}/repos/{repo}/tags",
                headers={**get_token_header(), **accept_json_header},
                params={"per_page": 100, "page": page_no},
            ).json()
            if len(response) == 0:
                break
            tags.extend(response)
            page_no += 1

    tags_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(tags_cache_file), "w") as f:
        f.write(json.dumps(tags))

    commits_cache_file = (
            Path(Config.get("gh_cache_path"))
            / repo.replace("/", "@")
            / f"{repo.replace('/', '@')}-commits.json"
    )
    if commits_cache_file.exists() and commits_cache_file.stat().st_size > 0:
        print(f"Read commits from cache at {commits_cache_file}")
        with open(str(commits_cache_file)) as f:
            commits = json.loads(f.read())

    else:
        page_no = 1
        commits = []
        while True:
            response = get(
                url=f"{Config.get('gh_api_base_url')}/repos/{repo}/commits",
                headers={**get_token_header(), **accept_json_header},
                params={"per_page": 100, "page": page_no},
            ).json()
            if len(response) == 0:
                break
            commits.extend(response)
            page_no += 1

    commits_cache_file.parent.mkdir(exist_ok=True, parents=True)
    with open(str(commits_cache_file), "w") as f:
        f.write(json.dumps(commits))

    commits = sorted(commits, key=lambda c: datetime.strptime(c["commit"]["committer"]["date"], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)

    release_tags = [r.tag for r in releases]
    sha_tags = {t["commit"]["sha"]: t["name"] for t in tags if t["name"] in release_tags}
    tag_and_parent = dict()

    print("Finding release parents")
    for s in tqdm(sha_tags.keys()):
        index_of_tag = next((i for i, elem in enumerate(commits) if elem["sha"] == s), None)
        if not index_of_tag:    # For some tags, the sha isn't found in the commit list
            tag_and_parent[sha_tags[s]] = None
            continue

        parent_shas = [p["sha"] for p in commits[index_of_tag]["parents"]]
        relevant_commits = commits[index_of_tag:]
        relevant_history = [c for c in relevant_commits if c["sha"] in parent_shas]

        preceding_tag_sha = None
        while not preceding_tag_sha and len(relevant_history) > 0:
            if relevant_history[0]["sha"] in sha_tags.keys():
                preceding_tag_sha = relevant_history[0]["sha"]
            else:
                if len(parent_shas) > 0 and relevant_history[0]["sha"] in parent_shas:
                    parent_shas.remove(relevant_history[0]["sha"])
                parent_shas.extend([p["sha"] for p in relevant_history[0]["parents"]])
                relevant_commits = relevant_commits[next((i for i, elem in enumerate(relevant_commits) if elem["sha"] == parent_shas[0]), 1):]
                relevant_history = [c for c in relevant_commits if c["sha"] in parent_shas]

        tag_and_parent[sha_tags[s]] = sha_tags[preceding_tag_sha] if preceding_tag_sha else None


    for t, p in tag_and_parent.items():
        print(f"{t}: {p}")
    return tag_and_parent






# get_release_tree()
