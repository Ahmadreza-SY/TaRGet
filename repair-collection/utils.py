import re
import hashlib


def save_file(content, file_path):
    if file_path.exists():
        return
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)


def is_test_class(file_content):
    junit_import = r"import\s+org\.junit\.(Test|\*|jupiter\.api\.(\*|Test))"
    test_annotation = r"@Test"
    return bool(re.search(junit_import, file_content)) and bool(re.search(test_annotation, file_content))


def get_hunk_lines(hunk):
    source_lines = set([c["lineNo"] for c in hunk.get("sourceChanges", [])])
    target_lines = set([c["lineNo"] for c in hunk.get("targetChanges", [])])
    return source_lines, target_lines


def get_java_diffs(commit, change_types=None):
    diffs = commit.diff(commit.parents[0].hexsha)
    if change_types is not None:
        diffs = [d for d in diffs if d.change_type in change_types]
    java_regex = r"^.*\.java$"
    diffs = [d for d in diffs if bool(re.search(java_regex, d.b_path)) and bool(re.search(java_regex, d.a_path))]
    return diffs


def hunk_to_string(hunk):
    output = ""
    for l in hunk.get("sourceChanges", []):
        output = output + f' - {l["line"]}'
    for l in hunk.get("targetChanges", []):
        output = output + f' + {l["line"]}'
    return output.strip()


def get_short_hash(s):
    return hashlib.sha256(s.encode()).hexdigest()[:8]
