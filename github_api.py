import requests
from pathlib import Path
import json

# import urllib.request
import requests
import shutil
from tqdm.auto import tqdm

# Global variables
api_base_url = "https://api.github.com"
raw_base_url = "https://raw.githubusercontent.com"
# TODO parametrize the token for security reasons
token_header = {"Authorization": "token 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"}
accept_diff_header = {"Accept": "application/vnd.github.v3.diff"}
accept_json_header = {"Accept": "application/vnd.github+json"}
cache_path = "./api_cache"


def get_diff(release_pair, repo):
    diff_pair = f"{release_pair.base.tag}...{release_pair.head.tag}"
    diff_cache_file = Path(cache_path) / f"{repo.replace('/', '@')}-{diff_pair}.diff"
    if diff_cache_file.exists() and diff_cache_file.stat().st_size > 0:
        print(f"Read diff from cache at {diff_cache_file}")
        with open(str(diff_cache_file)) as f:
            return f.read()

    print(f"Fetching {diff_pair} diff from GitHub")
    response = requests.get(
        f"{api_base_url}/repos/{repo}/compare/{diff_pair}",
        headers={**token_header, **accept_diff_header},
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
    response = requests.get(
        f"{raw_base_url}/{repo}/{tag}/{test_path}",
    )
    return response.text


def get_all_releases(repo):
    releases_cache_file = Path(cache_path) / f"{repo.replace('/', '@')}-releases.json"
    if releases_cache_file.exists() and releases_cache_file.stat().st_size > 0:
        print(f"Read releases from cache at {releases_cache_file}")
        with open(str(releases_cache_file)) as f:
            releases = json.loads(f.read())
            return releases

    page_no = 1
    releases = []
    print("Fetching all releases")
    while True:
        response = requests.get(
            f"{api_base_url}/repos/{repo}/releases",
            headers={**token_header, **accept_json_header},
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

    with requests.get(url, headers={**token_header}, stream=True) as r:
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
