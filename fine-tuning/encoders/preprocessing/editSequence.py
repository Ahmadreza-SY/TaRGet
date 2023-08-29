import difflib

REPLACE_OLD = "<replaceOld>"
REPLACE_NEW = "<replaceNew>"
REPLACE_END = "<replaceEnd>"
REPLACE_KEEP_BEFORE_OLD = "<replaceOldKeepBefore>"
REPLACE_KEEP_BEFORE_NEW = "<replaceNewKeepBefore>"
REPLACE_KEEP_AFTER_OLD = "<replaceOldKeepAfter>"
REPLACE_KEEP_AFTER_NEW = "<replaceNewKeepAfter>"
REPLACE_KEEP_BEFORE_AFTER_OLD = "<replaceOldKeepBeforeAfter>"
REPLACE_KEEP_BEFORE_AFTER_NEW = "<replaceNewKeepBeforeAfter>"
REPLACE_GROUP_OLD = "<replaceOldGroup>"
REPLACE_GROUP_NEW = "<replaceNewGroup>"

def build_edit_sequence(source, target):
    edit_sequence = []

    req_changes = find_token_diffs(source, target)
    all_replaces = True
    next_index = -1
    for index, change in [(i, c) for i, c in enumerate(req_changes) if c[0] != "equal"]:
        if index <= next_index:
            continue

        change_type, source_start, source_end, target_start, target_end = change
        replace_found = False

        # Only 1 possible replace in the source
        if source.count(source[source_start:source_end].strip()) == 1:
            edit_sequence.append(([REPLACE_OLD,
                                  source[source_start:source_end].strip(),
                                  REPLACE_NEW,
                                  target[target_start:target_end].strip(),
                                  REPLACE_END],
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

                    while source.count(f'{replace} {source[source_start:source_end].strip()}') > 1 and i >= 0:
                        replace = f'{preceding_tokens[i]} {replace}'
                        i -= 1

                    if source.count(f'{replace} {source[source_start:source_end].strip()}') == 1:
                        edit_sequence.append(([REPLACE_KEEP_BEFORE_OLD,
                                              f'{replace} {source[source_start:source_end].strip()}'.strip(),
                                              REPLACE_KEEP_BEFORE_NEW,
                                              f'{replace} {target[target_start:target_end].strip()}'.strip(),
                                              REPLACE_END],
                                              req_changes[index - 1][1], source_end,
                                              req_changes[index - 1][3], target_end))
                        replace_found = True

            # > 1 possible replace in the source, start appending tokens after the change to find a unique replace
            if not replace_found and index != len(req_changes) - 1:
                following_tokens = list(filter(None, source[req_changes[index + 1][1]:req_changes[index + 1][2]].split(' ')))

                if len(following_tokens) > 0:
                    replace = following_tokens[0]
                    i = 1

                    while source.count(f'{source[source_start:source_end].strip()} {replace}') > 1 and i <= len(following_tokens) - 1:
                        replace = f'{replace} {following_tokens[i]}'
                        i += 1

                    if source.count(f'{source[source_start:source_end]} {replace}') == 1:
                        edit_sequence.append(([REPLACE_KEEP_AFTER_OLD,
                                              f'{source[source_start:source_end].strip()} {replace}'.strip(),
                                              REPLACE_KEEP_AFTER_NEW,
                                              f'{target[target_start:target_end].strip()} {replace}'.strip(),
                                              REPLACE_END],
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

                    while source.count(f'{replace_before} {source[source_start:source_end].strip()} {replace_after}') > 1 and i <= len(following_tokens) - 1:
                        replace_after = f'{replace_after} {following_tokens[i]}'
                        replace_before = f'{preceding_tokens[-1-i]} {replace_before}'
                        i += 1

                    if source.count(f'{replace_before} {source[source_start:source_end].strip()} {replace_after}') == 1:
                        edit_sequence.append(([REPLACE_KEEP_BEFORE_AFTER_OLD,
                                              f'{replace_before} {source[source_start:source_end].strip()} {replace_after}'.strip(),
                                              REPLACE_KEEP_BEFORE_AFTER_NEW,
                                              f'{replace_before} {target[target_start:target_end].strip()} {replace_after}'.strip(),
                                              REPLACE_END],
                                              req_changes[index - 1][1], req_changes[index - 1][2],
                                              req_changes[index - 1][3], req_changes[index - 1][4]))
                        replace_found = True


        if not replace_found:
            print("new block")
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

                if not replace_found and prev_index > 1:
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
                edit_sequence.append(([REPLACE_GROUP_OLD,
                                      source[source_start:source_end],
                                      REPLACE_GROUP_NEW,
                                      target[target_start:target_end],
                                      REPLACE_END],
                                      source_start, source_end,
                                      target_start, target_end))
                next_index = new_next_index

        all_replaces = all_replaces and replace_found

    return ' '.join([e1 for e0 in edit_sequence for e1 in e0[0]]), all_replaces


def find_token_diffs(source, target):
    sm = difflib.SequenceMatcher(a=source, b=target)
    req_changes = sm.get_opcodes()
    final_changes = []

    index = 0
    while index < len(req_changes):
        change_type, source_start, source_end, target_start, target_end = req_changes[index]

        if index < len(req_changes) - 1:
            next_change = req_changes[index + 1]
        else:
            next_change = None

        if change_type == "equal":
            while source_start < source_end < len(source) and not source[source_end].isspace():
                source_end -= 1
                if next_change:
                    next_change = (next_change[0], next_change[1] - 1, next_change[2], next_change[3], next_change[4])

            while target_start < target_end < len(target) and not target[target_end].isspace():
                target_end -= 1
                if next_change:
                    next_change = (next_change[0], next_change[1], next_change[2], next_change[3] - 1, next_change[4])
        else:
            while source_end < len(source)  and not source[source_end].isspace():
                source_end += 1
                if next_change:
                    next_change = (next_change[0], next_change[1] + 1, next_change[2], next_change[3], next_change[4])
                    if next_change[1] >= next_change[2]:
                        next_t_start = next_change[3]
                        req_changes.pop(index + 1)
                        if index < len(req_changes) - 1:
                            next_change = req_changes[index + 1]
                            next_change = (next_change[0], next_change[1], next_change[2], next_t_start, next_change[4])
                        else:
                            next_change = None

            while target_end < len(target) and not target[target_end].isspace():
                target_end += 1
                if next_change:
                    next_change = (next_change[0], next_change[1], next_change[2], next_change[3] + 1, next_change[4])
                    if next_change[3] >= next_change[4]:
                        next_s_start = next_change[1]
                        req_changes.pop(index + 1)
                        if index < len(req_changes) - 1:
                            next_change = req_changes[index + 1]
                            next_change = (next_change[0], next_s_start, next_change[2], next_change[3], next_change[4])
                        else:
                            next_change = None

        if next_change:
            req_changes[index + 1] = next_change

        final_changes.append((change_type, source_start, source_end, target_start, target_end))
        index += 1

    return final_changes
