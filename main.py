from unidiff import PatchSet
import pickle
from pathlib import Path
import re
import pandas as pd
import github_api as ghapi
import jparser
from tqdm import trange, tqdm
import tarfile
import shutil

# Global variables
repo = "dbeaver/dbeaver"
output_path = "./data-v2"
jparser_path = "jparser.jar"


class Release:
    def __init__(self, name, tag, date, tarball_url):
        self.name = name
        self.tag = tag
        self.date = date
        self.tarball_url = tarball_url

    def __str__(self) -> str:
        return self.tag


class ReleasePair:
    def __init__(self, base, head):
        self.base = base
        self.head = head

    def __str__(self) -> str:
        return f"{self.base.tag}...{self.head.tag}"


def download_source_code(release):
    release_path = Path(output_path) / "releases" / release.tag
    release_path.mkdir(parents=True, exist_ok=True)
    code_path = release_path / "code"
    if code_path.exists():
        return code_path

    code_tar_file = release_path / f"{release.tag}.tar.gz"
    ghapi.download_file(release.tarball_url, code_tar_file)
    with tarfile.open(str(code_tar_file)) as f:
        f.extractall(str(release_path / "temp"))
    temp_code_path = list((release_path / "temp").glob("*"))[0]
    shutil.move(str(temp_code_path), str(code_path))
    shutil.rmtree(str(release_path / "temp"))
    return code_path


def fetch_patches(release_pair):
    base_code_path = download_source_code(release_pair.base)
    base_tests = jparser.find_test_classes(base_code_path)
    head_code_path = download_source_code(release_pair.head)
    head_tests = jparser.find_test_classes(head_code_path)
    release_test_path_set = set(
        base_tests["PATH"].values.tolist() + head_tests["PATH"].values.tolist()
    )
    diff = ghapi.get_diff(release_pair, repo)
    patches = PatchSet(diff)
    test_patches = [
        patch for patch in patches.modified_files if patch.path in release_test_path_set
    ]
    return patches, test_patches


def get_package_name(java_file_content):
    matches = re.compile("package (.+);").findall(java_file_content)
    if len(matches) == 1:
        return matches[0]
    return None


def get_test_out_path(tag, _class):
    return Path(output_path) / "releases" / tag / "changed_tests" / _class


def fetch_and_save_test_code(test_path, tag):
    file_content = ghapi.get_test_file(tag, test_path, repo)
    package_name = get_package_name(file_content)
    full_name = f"{package_name}.{Path(test_path.stem)}"
    test_out_path = get_test_out_path(tag, full_name)
    test_out_path.mkdir(parents=True, exist_ok=True)
    test_out_file = test_out_path / test_path.name
    with open(str(test_out_file), "w") as f:
        f.write(file_content)

    jparser.extract_test_methods(test_out_file)

    return full_name


def find_changed_methods(_class, release_pair):
    base_path = get_test_out_path(release_pair.base.tag, _class)
    head_path = get_test_out_path(release_pair.head.tag, _class)

    changed_methods = []
    for bm_path in (base_path / "methods").glob("*"):
        hm_path = head_path / "methods" / bm_path.name
        if hm_path.exists():
            with open(str(bm_path)) as f:
                bm_code = f.read()
            with open(str(hm_path)) as f:
                hm_code = f.read()
            if bm_code != hm_code:
                changed_methods.append(bm_path.name)
    return changed_methods


def create_test_release_info(release_pair, test_patches):
    def update_test_release_info(_class, path, release):
        test_release_info["class"].append(_class)
        test_release_info["path"].append(path)
        test_release_info["release_tag"].append(release.tag)
        test_release_info["release_date"].append(release.date)

    test_release_info = {
        "class": [],
        "path": [],
        "release_tag": [],
        "release_date": [],
    }
    for test_patch in test_patches:
        test_path = Path(test_patch.path)
        full_name = fetch_and_save_test_code(test_path, release_pair.head.tag)
        update_test_release_info(full_name, str(test_path), release_pair.head)
        if test_patch.is_rename:
            test_path = test_patch.source_file
            if test_path.startswith("a/") or test_path.startswith("b/"):
                test_path = test_path[2:]
            test_path = Path(test_path)
        full_name = fetch_and_save_test_code(test_path, release_pair.base.tag)
        update_test_release_info(full_name, str(test_path), release_pair.base)

    return pd.DataFrame(test_release_info)


def create_test_repair_info(release_pair, test_patches, test_release_info):
    path_to_class = dict(
        zip(
            test_release_info["path"].values.tolist(),
            test_release_info["class"].values.tolist(),
        )
    )
    test_repair_info = {"class": [], "method": [], "base_tag": [], "head_tag": []}
    for test_patch in test_patches:
        test_path = Path(test_patch.path)
        _class = path_to_class[str(test_path)]
        changed_methods = find_changed_methods(_class, release_pair)
        for method in changed_methods:
            test_repair_info["class"].append(_class)
            test_repair_info["method"].append(method)
            test_repair_info["base_tag"].append(release_pair.base.tag)
            test_repair_info["head_tag"].append(release_pair.head.tag)
    return pd.DataFrame(test_repair_info)


def extract_release_repairs(release_pair):
    patches, test_patches = fetch_patches(release_pair)

    test_release_info = create_test_release_info(release_pair, test_patches)
    test_repair_info = create_test_repair_info(
        release_pair, test_patches, test_release_info
    )

    if len(test_repair_info) > 0:
        repairs_path = (
            Path(output_path)
            / "repairs"
            / f"{release_pair.base.tag}...{release_pair.head.tag}"
        )
        repairs_path.mkdir(parents=True, exist_ok=True)
        pickle.dump(
            {"patches": patches, "test_patches": test_patches},
            open(str(repairs_path / "patches.pickle"), "wb"),
        )

    return test_release_info, test_repair_info


def analyze_release_and_repairs():
    releases = [
        Release(
            r["name"], r["tag_name"], pd.to_datetime(r["created_at"]), r["tarball_url"]
        )
        for r in ghapi.get_all_releases(repo)
    ]
    releases.sort(key=lambda r: r.date, reverse=True)
    rel_info_l = []
    rep_info_l = []
    # TODO temp range (first 30 release pairs)
    for i in trange(
        30,
        ncols=100,
        position=0,
        leave=True,
    ):
        head = releases[i]
        base = releases[i + 1]
        print()
        print(f"Analyzing release {base.tag}...{head.tag}")
        release_pair = ReleasePair(base, head)
        rel_info, rep_info = extract_release_repairs(release_pair)
        rel_info_l.append(rel_info)
        rep_info_l.append(rep_info)

    pd.concat(rel_info_l).to_csv(
        Path(output_path) / "releases" / "test_release_info.csv", index=False
    )
    pd.concat(rep_info_l).to_csv(
        Path(output_path) / "test_repair_info.csv", index=False
    )


def create_repaired_tc_call_graphs():
    repair_info = pd.read_csv(Path(output_path) / "test_repair_info.csv")
    base_tags = repair_info["base_tag"].unique()
    for base_tag in tqdm(
        base_tags, ncols=100, position=0, leave=True, desc="Creating call graphs"
    ):
        jparser.create_call_graphs(Path(output_path), base_tag)


def main():
    # analyze_release_and_repairs()
    create_repaired_tc_call_graphs()


# TODO create a super project which includes jparser and this file
if __name__ == "__main__":
    main()
