import difflib

REPLACE_OLD = "<replaceOld>"
REPLACE_NEW = "<replaceNew>"
REPLACE_END = "<replaceEnd>"
REPLACE_KEEP_BEFORE_OLD = "<replaceOldKeepBefore>"
REPLACE_KEEP_BEFORE_NEW = "<replaceNewKeepBefore>"
REPLACE_KEEP_AFTER_OLD = "<replaceOldKeepAfter>"
REPLACE_KEEP_AFTER_NEW = "<replaceNewKeepAfter>"

def build_edit_sequence(source, target):
    edit_sequence = []

    req_changes = find_token_diffs(source, target)
    all_replaces = True
    for index, change in [(i, c) for i, c in enumerate(req_changes) if c[0] != "equal"]:
        change_type, source_start, source_end, target_start, target_end = change
        replace_found = False

        if source.count(source[source_start:source_end].strip()) == 1:
            edit_sequence.extend([REPLACE_OLD,
                                  source[source_start:source_end].strip(),
                                  REPLACE_NEW,
                                  target[target_start:target_end].strip(),
                                  REPLACE_END])
            replace_found = True

        else:
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
                        edit_sequence.extend([REPLACE_KEEP_BEFORE_OLD,
                                              f'{replace} {source[source_start:source_end].strip()}'.strip(),
                                              REPLACE_KEEP_BEFORE_NEW,
                                              f'{replace} {target[target_start:target_end].strip()}'.strip(),
                                              REPLACE_END])
                        replace_found = True


            if not replace_found:
                if index == len(req_changes) - 1:
                    pass
                else:
                    following_tokens = list(filter(None, source[req_changes[index + 1][1]:req_changes[index + 1][2]].split(' ')))

                    if len(following_tokens) > 0:
                        replace = following_tokens[0]
                        i = 1

                        while source.count(f'{source[source_start:source_end]} {replace}') > 1 and i <= len(following_tokens) - 1:
                            replace = f'{replace} {following_tokens[i]}'
                            i += 1

                        if source.count(f'{source[source_start:source_end]} {replace}') == 1:
                            edit_sequence.extend([REPLACE_KEEP_AFTER_OLD,
                                                  f'{source[source_start:source_end].strip()} {replace}'.strip(),
                                                  REPLACE_KEEP_AFTER_NEW,
                                                  f'{target[target_start:target_end].strip()} {replace}'.strip(),
                                                  REPLACE_END])
                            replace_found = True

        all_replaces = all_replaces and replace_found

    return ' '.join(edit_sequence), all_replaces


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
