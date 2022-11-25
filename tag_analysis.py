from unidiff import PatchSet
import pickle
from pathlib import Path
import re
import pandas as pd
import github_api as ghapi
from config import Config
import jparser
import shutil


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

        changed_test_classes = self.create_changed_test_classes()
        repaired_test_methods = self.create_repaired_test_methods(changed_test_classes)

        if len(repaired_test_methods) > 0:
            self.save_patches()

        return changed_test_classes, repaired_test_methods

    def fetch_patches(self):
        base_code_path = ghapi.copy_tag_code(Config.get("repo"), self.base)
        base_tests = jparser.find_test_classes(base_code_path)
        head_code_path = ghapi.copy_tag_code(Config.get("repo"), self.head)
        head_tests = jparser.find_test_classes(head_code_path)

        if base_tests.empty or head_tests.empty:
            return None

        test_path_set = set(base_tests["PATH"].values.tolist() + head_tests["PATH"].values.tolist())
        diff = ghapi.get_local_diff(self, Config.get("repo"))
        patches = PatchSet(diff)
        test_patches = [patch for patch in patches.modified_files if patch.path in test_path_set]
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
        test_file, content = ghapi.get_test_file_local(tag.name, test_path, Config.get("repo"))

        package_name = None
        matches = re.compile("^package (.+);$", re.MULTILINE).findall(content)
        if len(matches) == 1:
            package_name = matches[0]
        elif len(matches) > 1:
            raise Exception(f"Could not find the package name in tag {tag} and test {test_path}")

        if package_name is None:
            full_name = Path(test_path).stem
        else:
            full_name = f"{package_name}.{Path(test_path).stem}"
        test_out_path = self.get_test_out_path(full_name, tag)
        test_out_path.mkdir(parents=True, exist_ok=True)
        test_out_file = test_out_path / test_path.name
        shutil.copyfile(str(test_file), str(test_out_file))

        jparser.extract_test_methods(test_out_file)

        return full_name

    def create_changed_test_classes(self):
        def update_changed_test_classes(_class, path, tag):
            changed_test_classes["class"].append(_class)
            changed_test_classes["path"].append(path)
            changed_test_classes["tag"].append(tag.name)
            changed_test_classes["date"].append(pd.to_datetime(tag.commit.committed_datetime))

        changed_test_classes = {
            "class": [],
            "path": [],
            "tag": [],
            "date": [],
        }
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            head_full_name = self.fetch_and_save_test_code(self.head, test_path)
            update_changed_test_classes(head_full_name, str(test_path), self.head)
            if test_patch.is_rename:
                test_path = test_patch.source_file
                if test_path.startswith("a/") or test_path.startswith("b/"):
                    test_path = test_path[2:]
                test_path = Path(test_path)
            base_full_name = self.fetch_and_save_test_code(self.base, test_path)
            update_changed_test_classes(base_full_name, str(test_path), self.base)

        return pd.DataFrame(changed_test_classes)

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

    def create_repaired_test_methods(self, changed_test_classes):
        path_to_class = dict(
            zip(
                changed_test_classes["path"].values.tolist(),
                changed_test_classes["class"].values.tolist(),
            )
        )
        repaired_test_methods = {"class": [], "method": [], "path": [], "base_tag": [], "head_tag": []}
        for test_patch in self.test_patches:
            test_path = Path(test_patch.path)
            _class = path_to_class[str(test_path)]
            changed_methods = self.find_changed_methods(_class)
            for method in changed_methods:
                repaired_test_methods["class"].append(_class)
                repaired_test_methods["method"].append(method)
                repaired_test_methods["path"].append(test_patch.path)
                repaired_test_methods["base_tag"].append(self.base.name)
                repaired_test_methods["head_tag"].append(self.head.name)
        return pd.DataFrame(repaired_test_methods)
