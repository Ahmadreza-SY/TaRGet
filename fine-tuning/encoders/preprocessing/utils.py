def get_hunk_lines(hunk):
    source_lines = []
    target_lines = []
    if "sourceChanges" in hunk:
        source_lines = [l["line"] for l in hunk["sourceChanges"]]
    if "targetChanges" in hunk:
        target_lines = [l["line"] for l in hunk["targetChanges"]]
    return source_lines, target_lines
