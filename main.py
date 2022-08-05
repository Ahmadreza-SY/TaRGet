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
import json
import argparse
from config import Config


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
    release_path = Path(Config.get("output_path")) / "releases" / release.tag
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
    diff = ghapi.get_diff(release_pair, Config.get("repo"))
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
    return Path(Config.get("output_path")) / "releases" / tag / "changed_tests" / _class


def fetch_and_save_test_code(test_path, tag):
    file_content = ghapi.get_test_file(tag, test_path, Config.get("repo"))
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
            Path(Config.get("output_path"))
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
        for r in ghapi.get_all_releases(Config.get("repo"))
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
        Path(Config.get("output_path")) / "releases" / "test_release_info.csv",
        index=False,
    )
    pd.concat(rep_info_l).to_csv(
        Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv",
        index=False,
    )


def create_repaired_tc_call_graphs():
    repair_info = pd.read_csv(
        Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv"
    )
    base_tags = repair_info["base_tag"].unique()
    for base_tag in tqdm(
        base_tags, ncols=100, position=0, leave=True, desc="Creating call graphs"
    ):
        jparser.create_call_graphs(Path(Config.get("output_path")), base_tag)


def get_call_graph(_class, method, tag):
    call_graph_path = (
        Path(Config.get("output_path"))
        / "releases"
        / tag
        / "call_graphs"
        / _class
        / f"{method}.json"
    )
    call_graph = {}
    with open(call_graph_path) as f:
        call_graph = json.loads(f.read())

    return call_graph


def get_test_file_coverage(_class, method, tag):
    all_tests = pd.read_csv(
        Path(Config.get("output_path")) / "releases" / tag / "tests.csv"
    )
    all_test_files = all_tests["PATH"].values.tolist()

    call_graph = get_call_graph(_class, method, tag)

    return set(
        [n["path"] for n in call_graph["nodes"] if n["path"] not in all_test_files]
    )


def get_release_changed_files(base_tag, head_tag):
    release_patches_path = (
        Path(Config.get("output_path"))
        / "repairs"
        / f"{base_tag}...{head_tag}"
        / "patches.pickle"
    )
    patches = pickle.load(open(str(release_patches_path), "rb"))
    return set([patch.path for patch in patches["patches"].modified_files])


def create_repaired_tc_change_coverage():
    repair_info = pd.read_csv(
        Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv"
    )

    change_coverage = []
    for _, r in tqdm(
        repair_info.iterrows(),
        total=len(repair_info),
        ncols=100,
        position=0,
        leave=True,
        desc="Creating test change coverage",
    ):
        _class, method, base_tag, head_tag = (
            r["class"],
            r["method"],
            r["base_tag"],
            r["head_tag"],
        )
        tc_coverage = get_test_file_coverage(_class, method, base_tag)
        changed_files = get_release_changed_files(base_tag, head_tag)
        tc_change_coverage = list(tc_coverage.intersection(changed_files))
        cov_per = len(tc_change_coverage) / len(tc_coverage)
        chn_per = len(tc_change_coverage) / len(changed_files)
        change_coverage.append(
            {
                "test": f"{_class}.{method}",
                "baseTag": base_tag,
                "headTag": head_tag,
                "covered_changed_files": tc_change_coverage,
                "coverage_percentage": f"{cov_per:.2f}",
                "change_percentage": f"{chn_per:.3f}",
            }
        )

    cov_output_file = (
        Path(Config.get("output_path")) / "repairs" / "test_change_coverage.json"
    )
    with open(cov_output_file, "w") as f:
        f.write(json.dumps(change_coverage))

    jparser.detect_changed_methods(Config.get("output_path"))


def get_test_method_coverage(_class, method, tag):
    call_graph = get_call_graph(_class, method, tag)
    return set([n["name"] for n in call_graph["nodes"]])


def create_dataset():
    repair_info = pd.read_csv(
        Path(Config.get("output_path")) / "repairs" / "test_repair_info.csv"
    )
    full_changed_methods = json.loads(
        (
            Path(Config.get("output_path"))
            / "repairs"
            / "test_coverage_changed_methods.json"
        ).read_text()
    )
    changed_methods = {r["baseTag"]: r["methodChanges"] for r in full_changed_methods}

    dataset = []
    test_paths = {}
    for _, r in tqdm(
        repair_info.iterrows(),
        total=len(repair_info),
        ncols=100,
        position=0,
        leave=True,
        desc="Creating dataset",
    ):
        _class, method, base_tag, head_tag = (
            r["class"],
            r["method"],
            r["base_tag"],
            r["head_tag"],
        )
        name = f"{_class}.{method}"
        if base_tag not in test_paths:
            tests = pd.read_csv(
                Path(Config.get("output_path")) / "releases" / base_tag / "tests.csv"
            )
            test_paths[base_tag] = dict(
                zip(tests["NAME"].values.tolist(), tests["PATH"].values.tolist())
            )
        path = test_paths[base_tag][_class]
        before_repair = (
            Path(Config.get("output_path"))
            / "releases"
            / base_tag
            / "changed_tests"
            / _class
            / "methods"
            / method
        ).read_text()
        after_repair = (
            Path(Config.get("output_path"))
            / "releases"
            / head_tag
            / "changed_tests"
            / _class
            / "methods"
            / method
        ).read_text()
        method_coverage = get_test_method_coverage(_class, method, base_tag)
        covered_changes = [
            change
            for change in changed_methods.get(base_tag, [])
            if change["name"] in method_coverage
        ]

        dataset.append(
            {
                "name": name,
                "path": path,
                "base_release_tag": base_tag,
                "head_release_tag": head_tag,
                "before_repair": before_repair,
                "after_repair": after_repair,
                "covered_changes": covered_changes,
            }
        )

    (Path(Config.get("output_path")) / "dataset.json").write_text(
        json.dumps(dataset), encoding="utf-8"
    )


def analyze_github_releases(args):
    Config.set("gh_api_token", args.api_token)
    analyze_release_and_repairs()


def create_test_repair_dataset(args):
    create_repaired_tc_call_graphs()
    create_repaired_tc_change_coverage()
    create_dataset()


def add_common_arguments(parser):
    parser.add_argument(
        "-r",
        "--repository",
        help="The login and name of the repo seperated by / (e.g., dbeaver/dbeaver)",
        type=str,
        required=True,
    )
    parser.add_argument(
        "-o",
        "--output-path",
        help="The directory to save resulting information and data",
        type=str,
        required=True,
    )


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers()

    gh_releases_parser = subparsers.add_parser(
        "gh_releases",
        help="Analyzes all releases in the given GitHub repository and finds test case repairs.",
    )
    gh_releases_parser.set_defaults(func=analyze_github_releases)
    add_common_arguments(gh_releases_parser)
    gh_releases_parser.add_argument(
        "-t",
        "--api-token",
        help="A GitHub API token for fetching releases, diff, and source code",
        type=str,
        required=True,
    )

    dataset_parser = subparsers.add_parser(
        "dataset",
        help="Creates a test case repair dataset that includes test code before and after repair plus SUT changes covered by tests cases across all releases",
    )
    dataset_parser.set_defaults(func=create_test_repair_dataset)
    add_common_arguments(dataset_parser)

    args = parser.parse_args()
    Config.set("repo", args.repository)
    Config.set("output_path", args.output_path)
    args.func(args)


# TODO parameterize input arguments, create global configuration, and refactor code (separate data_collection from main.py)
if __name__ == "__main__":
    main()
