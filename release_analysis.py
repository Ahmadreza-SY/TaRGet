from unidiff import PatchSet
import pickle
from pathlib import Path
import re
import pandas as pd
import github_api as ghapi
import jparser
import tarfile
import shutil
from config import Config
import jparser


class Release:
    def __init__(self, name, tag, date, tarball_url):
        self.name = name
        self.tag = tag
        self.date = date
        self.tarball_url = tarball_url

    def __str__(self) -> str:
        return self.tag

    def download_source_code(self):
        release_path = Path(Config.get("output_path")) / "releases" / self.tag
        release_path.mkdir(parents=True, exist_ok=True)
        code_path = release_path / "code"
        if code_path.exists():
            return code_path

        code_tar_file = release_path / f"{self.tag}.tar.gz"
        ghapi.download_file(self.tarball_url, code_tar_file)
        with tarfile.open(str(code_tar_file)) as f:
            f.extractall(str(release_path / "temp"))
        temp_code_path = list((release_path / "temp").glob("*"))[0]
        shutil.move(str(temp_code_path), str(code_path))
        shutil.rmtree(str(release_path / "temp"))
        return code_path

    def get_test_out_path(self, _class):
        return Path(Config.get("output_path")) / "releases" / self.tag / "changed_tests" / _class

    def fetch_and_save_test_code(self, test_path):
        file_content = ghapi.get_test_file(self.tag, test_path, Config.get("repo"))

        package_name = None
        matches = re.compile("package (.+);").findall(file_content)
        if len(matches) == 1:
            package_name = matches[0]

        full_name = f"{package_name}.{Path(test_path.stem)}"
        test_out_path = self.get_test_out_path(full_name)
        test_out_path.mkdir(parents=True, exist_ok=True)
        test_out_file = test_out_path / test_path.name
        with open(str(test_out_file), "w") as f:
            f.write(file_content)

        jparser.extract_test_methods(test_out_file)

        return full_name


class ReleasePair:
    def __init__(self, base, head):
        self.base = base
        self.head = head
        self.patches = None
        self.test_patches = None

    def __str__(self) -> str:
        return f"{self.base.tag}...{self.head.tag}"

    def extract_release_repairs(self):
        test_patches = self.fetch_patches()
        if test_patches is None:
            return pd.DataFrame(), pd.DataFrame()

        test_release_info = self.create_test_release_info()
        test_repair_info = self.create_test_repair_info(test_release_info)

        if len(test_repair_info) > 0:
            self.save_patches()

        return test_release_info, test_repair_info

    def fetch_patches(self):
        base_code_path = self.base.download_source_code()
        base_tests = jparser.find_test_classes(base_code_path)
        head_code_path = self.head.download_source_code()
        head_tests = jparser.find_test_classes(head_code_path)
        if base_tests.empty or head_tests.empty:
            return None
        release_test_path_set = set(base_tests["PATH"].values.tolist() + head_tests["PATH"].values.tolist())
        diff = ghapi.get_diff(self, Config.get("repo"))
        patches = PatchSet(diff)
        test_patches = [patch for patch in patches.modified_files if patch.path in release_test_path_set]
        self.patches = patches
        self.test_patches = test_patches
        return test_patches

    def save_patches(self):
        repairs_path = Path(Config.get("output_path")) / "repairs" / f"{self.base.tag}...{self.head.tag}"
        repairs_path.mkdir(parents=True, exist_ok=True)
        pickle.dump(
            {"patches": self.patches, "test_patches": self.test_patches},
            open(str(repairs_path / "patches.pickle"), "wb"),
        )

    def create_test_release_info(self):
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
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            full_name = self.head.fetch_and_save_test_code(test_path)
            update_test_release_info(full_name, str(test_path), self.head)
            if test_patch.is_rename:
                test_path = test_patch.source_file
                if test_path.startswith("a/") or test_path.startswith("b/"):
                    test_path = test_path[2:]
                test_path = Path(test_path)
            full_name = self.base.fetch_and_save_test_code(test_path)
            update_test_release_info(full_name, str(test_path), self.base)

        return pd.DataFrame(test_release_info)

    def find_changed_methods(self, _class):
        base_path = self.base.get_test_out_path(_class)
        head_path = self.head.get_test_out_path(_class)

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

    def create_test_repair_info(self, test_release_info):
        path_to_class = dict(
            zip(
                test_release_info["path"].values.tolist(),
                test_release_info["class"].values.tolist(),
            )
        )
        test_repair_info = {"class": [], "method": [], "path": [], "base_tag": [], "head_tag": []}
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            _class = path_to_class[str(test_path)]
            changed_methods = self.find_changed_methods(_class)
            for method in changed_methods:
                test_repair_info["class"].append(_class)
                test_repair_info["method"].append(method)
                test_repair_info["path"].append(test_patch.path)
                test_repair_info["base_tag"].append(self.base.tag)
                test_repair_info["head_tag"].append(self.head.tag)
        return pd.DataFrame(test_repair_info)


class TagPair:
    def __init__(self, base, head):
        self.base = base
        self.head = head
        self.patches = None
        self.test_patches = None

    def __str__(self) -> str:
        return f"{self.base.name}...{self.head.name}"

    def extract_tag_repairs(self):
        test_patches = self.fetch_patches()
        if test_patches is None:
            return pd.DataFrame(), pd.DataFrame()

        test_release_info = self.create_test_release_info()
        test_repair_info = self.create_test_repair_info(test_release_info)

        if len(test_repair_info) > 0:
            self.save_patches()

        return test_release_info, test_repair_info

    def fetch_patches(self):
        base_code_path = ghapi.copy_tag_code(Config.get("repo"), self.base)
        base_tests = jparser.find_test_classes(base_code_path)
        head_code_path = ghapi.copy_tag_code(Config.get("repo"), self.head)
        head_tests = jparser.find_test_classes(head_code_path)

        if base_tests.empty or head_tests.empty:
            return None

        release_test_path_set = set(base_tests["PATH"].values.tolist() + head_tests["PATH"].values.tolist())
        diff = ghapi.get_local_diff(self, Config.get("repo"))
        patches = PatchSet(diff)
        test_patches = [patch for patch in patches.modified_files if patch.path in release_test_path_set]
        self.patches = patches
        self.test_patches = test_patches
        return test_patches

    def get_test_out_path(self, _class, tag):
        return Path(Config.get("output_path")) / "tags" / tag.name / "changed_tests" / _class

    def save_patches(self):
        repairs_path = Path(Config.get("output_path")) / "repairs" / f"{self.base.name}...{self.head.name}"
        repairs_path.mkdir(parents=True, exist_ok=True)
        pickle.dump(
            {"patches": self.patches, "test_patches": self.test_patches},
            open(str(repairs_path / "patches.pickle"), "wb"),
        )

    def fetch_and_save_test_code(self, tag, test_path):
        # start here
        content = ghapi.get_test_file_local(tag.name, test_path, Config.get("repo"))

        package_name = None
        matches = re.compile("package (.+);").findall(content)
        if len(matches) == 1:
            package_name = matches[0]

        full_name = f"{package_name}.{Path(test_path.stem)}"
        test_out_path = self.get_test_out_path(full_name, tag)
        test_out_path.mkdir(parents=True, exist_ok=True)
        test_out_file = test_out_path / test_path.name
        with open(str(test_out_file), "w") as f:
            f.write(content)

        jparser.extract_test_methods(test_out_file)

        return full_name

    def create_test_release_info(self):
        def update_test_release_info(_class, path, tag):
            test_release_info["class"].append(_class)
            test_release_info["path"].append(path)
            test_release_info["release_tag"].append(tag.name)
            test_release_info["release_date"].append(tag.commit.committed_date)

        test_release_info = {
            "class": [],
            "path": [],
            "release_tag": [],
            "release_date": [],
        }
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            head_full_name = self.fetch_and_save_test_code(self.head, test_path)
            update_test_release_info(head_full_name, str(test_path), self.head)
            if test_patch.is_rename:
                test_path = test_patch.source_file
                if test_path.startswith("a/") or test_path.startswith("b/"):
                    test_path = test_path[2:]
                test_path = Path(test_path)
            base_full_name = self.fetch_and_save_test_code(self.base, test_path)
            update_test_release_info(base_full_name, str(test_path), self.base)

        return pd.DataFrame(test_release_info)

    def find_changed_methods(self, _class):
        base_path = self.get_test_out_path(_class, self.base)
        head_path = self.get_test_out_path(_class, self.head)

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

    def create_test_repair_info(self, test_release_info):
        path_to_class = dict(
            zip(
                test_release_info["path"].values.tolist(),
                test_release_info["class"].values.tolist(),
            )
        )
        test_repair_info = {"class": [], "method": [], "path": [], "base_tag": [], "head_tag": []}
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            _class = path_to_class[str(test_path)]
            changed_methods = self.find_changed_methods(_class)
            for method in changed_methods:
                test_repair_info["class"].append(_class)
                test_repair_info["method"].append(method)
                test_repair_info["path"].append(test_patch.path)
                test_repair_info["base_tag"].append(self.base.name)
                test_repair_info["head_tag"].append(self.head.name)
        return pd.DataFrame(test_repair_info)