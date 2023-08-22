def line_is_comment(line):
    clean_line = line.strip().replace(" ", "")
    prefixes = ["//", "/*", "*"]
    suffixes = ["*/"]
    return any([clean_line.startswith(p) for p in prefixes]) or any([clean_line.endswith(s) for s in suffixes])


def hunk_is_empty(hunk):
    if "sourceChanges" in hunk and len(hunk["sourceChanges"]) > 0:
        return False
    if "targetChanges" in hunk and len(hunk["targetChanges"]) > 0:
        return False
    return True


def remove_hunk_comments(hunk):
    if "sourceChanges" in hunk:
        hunk["sourceChanges"] = [l for l in hunk["sourceChanges"] if not line_is_comment(l["line"])]
    if "targetChanges" in hunk:
        hunk["targetChanges"] = [l for l in hunk["targetChanges"] if not line_is_comment(l["line"])]
    return hunk


def remove_covered_changes_comments(covered_changes):
    for c in covered_changes:
        c["hunks"] = [remove_hunk_comments(h) for h in c["hunks"]]
        c["hunks"] = [h for h in c["hunks"] if not hunk_is_empty(h)]

    covered_changes = [c for c in covered_changes if len(c["hunks"]) > 0]
    return covered_changes


def _remove_empty_hunks(sut_changes):
    for c in sut_changes:
        c["hunks"] = [h for h in c["hunks"] if not hunk_is_empty(h)]
    sut_changes = [c for c in sut_changes if len(c["hunks"]) > 0]
    return sut_changes
