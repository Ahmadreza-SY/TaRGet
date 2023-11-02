def get_hunk_lines(hunk):
    source_lines = []
    target_lines = []
    if "sourceChanges" in hunk:
        source_lines = [l["line"] for l in hunk["sourceChanges"]]
    if "targetChanges" in hunk:
        target_lines = [l["line"] for l in hunk["targetChanges"]]
    return source_lines, target_lines


def get_hunk_line_numbers(hunk):
    source_lines = [c["lineNo"] for c in hunk.get("sourceChanges", [])]
    target_lines = [c["lineNo"] for c in hunk.get("targetChanges", [])]
    return source_lines, target_lines


def get_hunk_location(hunk):
    src_lines, tgt_lines = get_hunk_line_numbers(hunk)
    src_loc = src_lines[0] if len(src_lines) > 0 else "null"
    tgt_loc = tgt_lines[0] if len(tgt_lines) > 0 else "null"
    return f"({src_loc}:{tgt_loc})"
