import difflib
import re
from encoders.testRepair import Tokens
from encoders.preprocessing.codeFormatter import add_padding_to_chars


REPLACE_OLDS = [Tokens.REPLACE_OLD, Tokens.REPLACE_KEEP_BEFORE_OLD, Tokens.REPLACE_KEEP_AFTER_OLD, Tokens.REPLACE_KEEP_BEFORE_AFTER_OLD, Tokens.REPLACE_GROUP_OLD]
REPLACE_NEWS = [Tokens.REPLACE_NEW, Tokens.REPLACE_KEEP_BEFORE_NEW, Tokens.REPLACE_KEEP_AFTER_NEW, Tokens.REPLACE_KEEP_BEFORE_AFTER_NEW, Tokens.REPLACE_GROUP_NEW]

def build_edit_sequence(source, target):
    edit_sequence = []

    source = add_padding_to_chars(source)
    target = add_padding_to_chars(target)

    req_changes = find_token_diffs(source, target)
    all_replaces = True
    next_index = -1
    for index, change in [(i, c) for i, c in enumerate(req_changes) if c[0] != "equal"]:
        if index <= next_index:
            continue

        change_type, source_start, source_end, target_start, target_end = change
        replace_found = False

        # Only 1 possible replace in the source
        if source.count(source[source_start:source_end]) == 1:
            edit_sequence.append(([Tokens.REPLACE_OLD,
                                  source[source_start:source_end],
                                  Tokens.REPLACE_NEW,
                                  target[target_start:target_end],
                                  Tokens.REPLACE_END],
                                  source_start, source_end,
                                  target_start, target_end))
            replace_found = True

        else:
            # > 1 possible replace in the source, start appending tokens before the change to find a unique replace
            if index != 0:
                preceding_tokens = list(filter(None, source[req_changes[index - 1][1]:req_changes[index - 1][2]].split(' ')))

                if len(preceding_tokens) > 0:
                    i = len(preceding_tokens) - 1
                    replace = preceding_tokens[i]
                    i -= 1

                    source_to_replace = (' ' if source_start != source_end else '') + source[source_start:source_end]
                    while source.count(f'{replace}{source_to_replace}') > 1 and i >= 0:
                        replace = f'{preceding_tokens[i]} {replace}'
                        i -= 1

                    if source.count(f'{replace} {source[source_start:source_end]}') == 1:
                        edit_sequence.append(([Tokens.REPLACE_KEEP_BEFORE_OLD,
                                              f'{replace}{source_to_replace}',
                                              Tokens.REPLACE_KEEP_BEFORE_NEW,
                                              f'{replace} {target[target_start:target_end]}',
                                              Tokens.REPLACE_END],
                                              req_changes[index - 1][1], source_end,
                                              req_changes[index - 1][3], target_end))
                        replace_found = True

            # > 1 possible replace in the source, start appending tokens after the change to find a unique replace
            if not replace_found and index != len(req_changes) - 1:
                following_tokens = list(filter(None, source[req_changes[index + 1][1]:req_changes[index + 1][2]].split(' ')))

                if len(following_tokens) > 0:
                    replace = following_tokens[0]
                    i = 1

                    source_to_replace = source[source_start:source_end] + (' ' if source_start != source_end else '')
                    while source.count(f'{source_to_replace}{replace}') > 1 and i <= len(following_tokens) - 1:
                        replace = f'{replace} {following_tokens[i]}'
                        i += 1

                    if source.count(f'{source[source_start:source_end]} {replace}') == 1:
                        edit_sequence.append(([Tokens.REPLACE_KEEP_AFTER_OLD,
                                              f'{source_to_replace}{replace}',
                                              Tokens.REPLACE_KEEP_AFTER_NEW,
                                              f'{target[target_start:target_end]} {replace}',
                                              Tokens.REPLACE_END],
                                              source_start, req_changes[index - 1][2],
                                              target_start, req_changes[index - 1][4]))
                        replace_found = True

            # > 1 possible replace in the source, start appending tokens before and after the change to find a unique replace
            if not replace_found and index != len(req_changes) - 1 and index != 0:
                preceding_tokens = list(filter(None, source[req_changes[index - 1][1]:req_changes[index - 1][2]].split(' ')))
                following_tokens = list(filter(None, source[req_changes[index + 1][1]:req_changes[index + 1][2]].split(' ')))

                if len(preceding_tokens) > 0 and len(following_tokens) > 0:
                    replace_before = preceding_tokens[-1]
                    replace_after = following_tokens[0]
                    i = 1

                    source_to_replace = (' ' if source_start != source_end else '') + source[source_start:source_end] + (' ' if source_start != source_end else '')
                    while source.count(f'{replace_before}{source_to_replace}{replace_after}') > 1:
                        if i < len(following_tokens):
                            replace_after = f'{replace_after} {following_tokens[i]}'
                        if i < len(preceding_tokens):
                            replace_before = f'{preceding_tokens[-1-i]} {replace_before}'
                        i += 1
                        if i >= len(following_tokens) and i >= len(preceding_tokens):
                            break

                    if source.count(f'{replace_before} {source[source_start:source_end]} {replace_after}') == 1:
                        edit_sequence.append(([Tokens.REPLACE_KEEP_BEFORE_AFTER_OLD,
                                              f'{replace_before}{source_to_replace}{replace_after}',
                                              Tokens.REPLACE_KEEP_BEFORE_AFTER_NEW,
                                              f'{replace_before} {target[target_start:target_end]} {replace_after}',
                                              Tokens.REPLACE_END],
                                              req_changes[index - 1][1], req_changes[index - 1][2],
                                              req_changes[index - 1][3], req_changes[index - 1][4]))
                        replace_found = True


        if not replace_found:
            replace_source, replace_target = source[source_start:source_end], target[target_start:target_end]
            new_next_index, prev_index, to_be_removed = index, index, 0

            while not replace_found and (new_next_index < len(req_changes) - 2 or prev_index >= 1):
                if new_next_index < len(req_changes) - 2:
                    next_equal = req_changes[new_next_index + 1]
                    replace_source += source[next_equal[1]:next_equal[2]]
                    replace_target += target[next_equal[3]:next_equal[4]]

                    next_change = req_changes[new_next_index + 2]
                    replace_source += source[next_change[1]:next_change[2]]
                    replace_target += target[next_change[3]:next_change[4]]

                    source_end = next_change[2]
                    target_end = next_change[4]
                    new_next_index += 2

                    if source.count(replace_source) == 1:
                        replace_found = True

                if not replace_found and prev_index >= 1:
                    prev_equal = req_changes[prev_index - 1]
                    replace_source = source[prev_equal[1]:prev_equal[2]] + replace_source
                    replace_target = target[prev_equal[3]:prev_equal[4]] + replace_target

                    prev_change = req_changes[prev_index - 2]
                    replace_source = source[prev_change[1]:prev_change[2]] + replace_source
                    replace_target = target[prev_change[3]:prev_change[4]] + replace_target

                    source_start = prev_change[1]
                    target_start = prev_change[3]
                    prev_index -= 2

                    if source.count(replace_source) == 1:
                        replace_found = True

            if replace_found:
                count = 0
                for l, ss, se, ts, te in edit_sequence[::-1]:
                    if se >= source_start or te >= target_start:
                        source_start = ss
                        target_start = ts
                        count += 1

                edit_sequence = edit_sequence[:len(edit_sequence)-count]
                edit_sequence.append(([Tokens.REPLACE_GROUP_OLD,
                                      source[source_start:source_end],
                                      Tokens.REPLACE_GROUP_NEW,
                                      target[target_start:target_end],
                                      Tokens.REPLACE_END],
                                      source_start, source_end,
                                      target_start, target_end))
                next_index = new_next_index

        all_replaces = all_replaces and replace_found

    i = 0
    while i < len(edit_sequence) - 1:
        curr_e = edit_sequence[i]
        next_e = edit_sequence[i + 1]

        while next_e and curr_e[2] > next_e[1]:
            curr_e = ([Tokens.REPLACE_GROUP_OLD,
                      source[curr_e[1]:next_e[2]],
                      Tokens.REPLACE_GROUP_NEW,
                      target[curr_e[3]:next_e[4]],
                      Tokens.REPLACE_END],
                      curr_e[1], next_e[2], curr_e[3], next_e[4])

            if i+1 < len(edit_sequence):
                del edit_sequence[i + 1]
            if i+1 < len(edit_sequence):
                next_e = edit_sequence[i + 1]
            else:
                next_e = None

        edit_sequence[i] = curr_e
        i += 1

    for i in range(len(edit_sequence)):
        edit, _, _, _, _ = edit_sequence[i]
        token1, s, token2, t, token3 = edit
        if not s in source:
            new_s = add_padding_to_chars(s)
            if new_s in source:
                s = new_s
            else:
                all_replaces = False

        if not t in target:
            new_t = add_padding_to_chars(t)
            if new_t in target:
                t = new_t
            else:
                all_replaces = False

        edit_sequence[i] = ([token1, s, token2, t, token3],)

    return ' '.join([e1 for e0 in edit_sequence for e1 in e0[0]]), all_replaces


def find_token_diffs(source, target):
    sm = difflib.SequenceMatcher(a=source, b=target)
    req_changes = sm.get_opcodes()
    final_changes = []

    index = 0
    while index < len(req_changes):
        change_type, source_start, source_end, target_start, target_end = req_changes[index]

        source_start_space = source_start >= len(source) or source_start <= 0 or source[source_start - 1].isspace() or source[source_start].isspace()
        source_end_space = source_end >= len(source) or source_end <= 0 or (source[source_end - 1].isspace() and source_end != source_start) or source[source_end].isspace()
        source_surrounded_by_spaces = source_start_space and source_end_space

        target_start_space = target_start >= len(target) or target_start <= 0 or target[target_start - 1].isspace() or target[target_start].isspace()
        target_end_space = target_end >= len(target) or target_end <= 0 or (target[target_end - 1].isspace() and target_start != target_end) or target[target_end].isspace()
        target_surrounded_by_spaces = target_start_space and target_end_space

        if index < len(req_changes) - 1:
            next_change = req_changes[index + 1]
        else:
            next_change = None

        if change_type == "equal":
            while source_start < source_end < len(source) and (not source_end_space or (next_change and next_change[0] == "insert" and not target_surrounded_by_spaces)):
                source_end -= 1
                source_end_space = source_end >= len(source) or source_end <= 0 or (source[source_end - 1].isspace() and source_end != source_start) or source[source_end].isspace()
                target_end -= 1
                target_end_space = target_end >= len(target) or target_end <= 0 or (target[target_end - 1].isspace() and target_start != target_end) or target[target_end].isspace()
                target_surrounded_by_spaces = target_start_space and target_end_space

                if next_change:
                    next_change = (next_change[0], next_change[1] - 1, next_change[2], next_change[3] - 1, next_change[4])

        else:
            check_source = True
            target_changed = False
            while check_source:
                while source_end < len(source) and not (source_end_space or (change_type == "insert" and target_surrounded_by_spaces and source_start == source_end)):
                    source_end += 1
                    source_end_space = source_end >= len(source) or source_end <= 0 or (source[source_end - 1].isspace() and source_end != source_start) or source[source_end].isspace()
                    source_surrounded_by_spaces = source_start_space and source_end_space

                    if change_type == "delete" and not target_changed:
                        target_end += 1

                    if next_change:
                        next_change = (next_change[0], next_change[1] + 1, next_change[2], next_change[3] + (1 if change_type == "delete" else 0), next_change[4])
                        if next_change[1] >= next_change[2]:
                            target_end = next_change[4]
                            target_end_space = target_end >= len(target) or target_end <= 0 or (target[target_end - 1].isspace() and target_start != target_end) or target[target_end].isspace()
                            target_surrounded_by_spaces = target_start_space and target_end_space

                            req_changes.pop(index + 1)
                            if index < len(req_changes) - 1:
                                next_change = req_changes[index + 1]
                                next_change = (next_change[0], next_change[1], next_change[2], target_end, next_change[4])
                            else:
                                next_change = None
                check_source = False

                while target_start != target_end < len(target) and not (target_end_space or (change_type == "delete" and source_surrounded_by_spaces and target_start == target_end)):
                    target_end += 1
                    target_end_space = target_end >= len(target) or target_end <= 0 or (target[target_end - 1].isspace() and target_start != target_end) or target[target_end].isspace()
                    target_changed = True

                    if change_type == "delete":
                        source_end += 1

                    if next_change:
                        next_change = (next_change[0], next_change[1] + (1 if change_type == "insert" else 0), next_change[2], next_change[3] + 1, next_change[4])
                        if next_change[3] >= next_change[4]:
                            source_end = next_change[2]
                            source_end_space = source_end >= len(source) or source_end <= 0 or (source[source_end - 1].isspace() and source_end != source_start) or source[source_end].isspace()
                            source_surrounded_by_spaces = source_start_space and source_end_space
                            check_source = True

                            req_changes.pop(index + 1)
                            if index < len(req_changes) - 1:
                                next_change = req_changes[index + 1]
                                next_change = (next_change[0], source_end, next_change[2], next_change[3], next_change[4])
                            else:
                                next_change = None

        append_curr = True
        if next_change:
            if change_type == "equal" and source_end - source_start != target_end - target_start:
                append_curr = False
                if next_change:
                    req_changes[index + 1]  = (next_change[0], source_start, next_change[2], target_start, next_change[4])
                else:
                    prev_change = req_changes[index - 1]
                    prev_change = (prev_change[0], prev_change[1], source_end, prev_change[3], target_end)
                    req_changes[index - 1] = prev_change
            else:
                req_changes[index + 1] = (next_change[0], source_end, next_change[2], target_end, next_change[4])

        if append_curr:
            final_changes.append((change_type, source_start, source_end, target_start, target_end))
        index += 1

    final_changes = [f for f in final_changes if not (f[1] >= f[2] and f[3] >= f[4])]

    i = 0
    while i < len(final_changes) - 1:
        curr_e = final_changes[i]

        next_e = final_changes[i + 1]
        if curr_e[1] == curr_e[2] and target[curr_e[4] - 1] == ' ':
            curr_e = (curr_e[0], curr_e[1], next_e[2], curr_e[3], next_e[4])
            del final_changes[i+1]
            next_e = None

        if i < len(final_changes) - 1:
            next_e = final_changes[i + 1]

        while next_e and (curr_e[0] == next_e[0] == "equal" or (curr_e[0] != "equal" and next_e[0] != "equal")):
            curr_e = ("equal" if curr_e[0] == "equal" else "replace", curr_e[1], next_e[2], curr_e[3], next_e[4])

            if i+1 < len(final_changes):
                del final_changes[i + 1]
            if i+1 < len(final_changes):
                next_e = final_changes[i + 1]
            else:
                next_e = None

        final_changes[i] = curr_e
        i += 1

    return final_changes


def apply_edit_sequence(original_code, edit_seq, replace_pairs=None):
    if not replace_pairs:
        replace_pairs = get_replace_pairs(edit_seq)

    if not replace_pairs:
        return None

    original_code = add_padding_to_chars(original_code)
    last_index = len(original_code)

    for orig, new in reversed(replace_pairs):
        if orig is None or new is None or original_code[:last_index+len(orig)-1].count(orig) != 1:
            return None

        last_index = original_code.index(orig)
        original_code = original_code.replace(orig, new, 1)

    return original_code


def get_replace_pairs(edit_seq):
    if Tokens.REPLACE_END not in edit_seq:
        return None

    replaces = [r for r in edit_seq.split(f' {Tokens.REPLACE_END}') if r]
    pairs = []

    for r in replaces:
        orig, new = None, None
        old_found = False
        for old in REPLACE_OLDS:
            if old in r:
                r = re.sub(f'\s*{re.escape(old)} ', '', r)
                old_found = True
                break

        if not old_found:
            return None

        for new in REPLACE_NEWS:
            if new in r:
                blocks = re.split(f' {re.escape(new)} ', r)
                if len(blocks) == 2:
                    orig, new = blocks[0], blocks[1]
                break

        if not orig or not new:
            return None

        pairs.append((orig, new))

    return pairs
