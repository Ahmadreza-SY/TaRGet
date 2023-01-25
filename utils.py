import re


def auto_str(cls):
    def __str__(self):
        return "%s(%s)" % (type(self).__name__, ", ".join("%s=%s" % item for item in vars(self).items()))

    cls.__str__ = __str__
    return cls


def save_file(content, file_path):
    if file_path.exists():
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def decompose_full_method_name(full_method_name):
    items = full_method_name.split(".")
    class_full_name = ".".join(items[:-1])
    class_name = items[-2]
    method_short_name = re.sub("\(.*\)", "", items[-1])
    return class_full_name, class_name, method_short_name


def is_test_class(file_content):
    junit_import = r"import\s+org\.junit\.(Test|\*|jupiter\.api\.(\*|Test))"
    test_annotation = r"@Test"
    return bool(re.search(junit_import, file_content)) and bool(re.search(test_annotation, file_content))


def get_hunk_lines(hunk):
    source_lines = set([c["lineNo"] for c in hunk.get("sourceChanges", [])])
    target_lines = set([c["lineNo"] for c in hunk.get("targetChanges", [])])
    return source_lines, target_lines


def get_java_diffs(commit, change_types=["R", "M"]):
    diffs = commit.diff(commit.parents[0].hexsha)
    diffs = [d for d in diffs if d.change_type in change_types]
    java_regex = r"^.*\.java$"
    diffs = [d for d in diffs if bool(re.search(java_regex, d.b_path)) and bool(re.search(java_regex, d.a_path))]
    return diffs


def no_covered_changes(repair):
    class_hunks_cnt = sum([len(change["hunks"]) for change in repair["coveredClassChanges"]])
    method_hunks_cnt = sum([len(change["hunks"]) for change in repair["coveredMethodChanges"]])
    return (class_hunks_cnt + method_hunks_cnt) == 0


def hunk_to_string(hunk):
    output = ""
    for l in hunk.get("sourceChanges", []):
        output = output + f' - {l["line"]}'
    for l in hunk.get("targetChanges", []):
        output = output + f' + {l["line"]}'
    return output.strip()
