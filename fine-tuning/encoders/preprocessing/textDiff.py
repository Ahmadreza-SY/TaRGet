from diff_match_patch import diff_match_patch
from encoders.preprocessing.utils import get_hunk_lines


def diff_wordsToChars(text1, text2):
    lineArray = []
    lineHash = {}
    lineArray.append("")

    def diff_linesToCharsMunge(text):
        chars = []
        lineStart = 0
        lineEnd = -1
        while lineEnd < len(text) - 1:
            lineEnd = text.find(" ", lineStart)
            if lineEnd == -1:
                lineEnd = len(text) - 1
            line = text[lineStart : lineEnd + 1]

            if line in lineHash:
                chars.append(chr(lineHash[line]))
            else:
                if len(lineArray) == maxLines:
                    line = text[lineStart:]
                    lineEnd = len(text)
                lineArray.append(line)
                lineHash[line] = len(lineArray) - 1
                chars.append(chr(len(lineArray) - 1))
            lineStart = lineEnd + 1
        return "".join(chars)

    maxLines = 666666
    chars1 = diff_linesToCharsMunge(text1)
    maxLines = 1114111
    chars2 = diff_linesToCharsMunge(text2)
    return (chars1, chars2, lineArray)


def get_word_diffs(source, target):
    dmp = diff_match_patch()
    (source, target, linearray) = diff_wordsToChars(source, target)
    diffs = dmp.diff_main(source, target, False, None)
    dmp.diff_charsToLines(diffs, linearray)
    diffs = [d for d in diffs if not d[1].isspace()]
    return diffs


def get_hunk_diffs(hunk):
    source_lines, target_lines = get_hunk_lines(hunk)
    source = " ".join(source_lines)
    target = " ".join(target_lines)
    return get_word_diffs(source, target)


def is_whitespace_hunk(hunk):
    diffs = get_hunk_diffs(hunk)
    change_cnt = sum([1 for type, _ in diffs if type in [diff_match_patch.DIFF_INSERT, diff_match_patch.DIFF_DELETE]])
    return change_cnt == 0


def remove_whitespace_hunks(sut_changes):
    for c in sut_changes:
        hunks = []
        for h in c["hunks"]:
            if not is_whitespace_hunk(h):
                hunks.append(h)
        c["hunks"] = hunks
    sut_changes = [c for c in sut_changes if len(c["hunks"]) > 0]
    return sut_changes
