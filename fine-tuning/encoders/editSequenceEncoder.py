import difflib
import re
from encoders.preprocessing.codeFormatter import add_padding_to_chars
from encoders.wordLevelEncoder import WordLevelDataEncoder, WordLevelTokens


class EditSeqTokens(WordLevelTokens):
    REPLACE_OLD = "[<replaceOld>]"
    REPLACE_NEW = "[<replaceNew>]"
    REPLACE_KEEP_BEFORE_OLD = "[<replaceOldKeepBefore>]"
    REPLACE_KEEP_BEFORE_NEW = "[<replaceNewKeepBefore>]"
    REPLACE_KEEP_AFTER_OLD = "[<replaceOldKeepAfter>]"
    REPLACE_KEEP_AFTER_NEW = "[<replaceNewKeepAfter>]"
    REPLACE_KEEP_BEFORE_AFTER_OLD = "[<replaceOldKeepBeforeAfter>]"
    REPLACE_KEEP_BEFORE_AFTER_NEW = "[<replaceNewKeepBeforeAfter>]"
    REPLACE_GROUP_OLD = "[<replaceOldGroup>]"
    REPLACE_GROUP_NEW = "[<replaceNewGroup>]"
    REPLACE_END = "[<replaceEnd>]"


REPLACE_OLDS = [
    EditSeqTokens.REPLACE_OLD,
    EditSeqTokens.REPLACE_KEEP_BEFORE_OLD,
    EditSeqTokens.REPLACE_KEEP_AFTER_OLD,
    EditSeqTokens.REPLACE_KEEP_BEFORE_AFTER_OLD,
    EditSeqTokens.REPLACE_GROUP_OLD,
]
REPLACE_NEWS = [
    EditSeqTokens.REPLACE_NEW,
    EditSeqTokens.REPLACE_KEEP_BEFORE_NEW,
    EditSeqTokens.REPLACE_KEEP_AFTER_NEW,
    EditSeqTokens.REPLACE_KEEP_BEFORE_AFTER_NEW,
    EditSeqTokens.REPLACE_GROUP_NEW,
]


class EditSequenceDataEncoder(WordLevelDataEncoder):
    def get_special_tokens_class(self):
        return EditSeqTokens

    def create_output(self, row):
        repaired = self.get_repaired_code(row)
        broken = self.get_broken_code(row)

        edit_seq, success = build_edit_sequence(broken, repaired)
        applied = None

        if success:
            applied = apply_edit_sequence(broken, edit_seq)

        if not applied or applied != repaired:
            edit_seq = get_default_edit_sequence(broken, repaired)
            row["invalid_eseq"] = True

        return edit_seq

    def get_target_change(self, row):
        target_change = self.get_repaired_code(row)
        return target_change.strip()

    def create_inputs_and_outputs(self, ds):
        ds["invalid_eseq"] = False
        ds = super(EditSequenceDataEncoder, self).create_inputs_and_outputs(ds)
        ds["target_change"] = ds.apply(lambda r: self.get_target_change(r), axis=1)
        invalid_cnt = len(ds[ds["invalid_eseq"]])
        self.log(
            f"Found {invalid_cnt} cases ({round(100 * invalid_cnt / len(ds), 2)} %) where edit sequence could not be generated or was not successfully applied."
        )
        return ds

    @staticmethod
    def remove_special_tokens(edit_seq, tokenizer):
        new_edit_seq = ""
        tokens = []
        for _, v in tokenizer.special_tokens_map.items():
            if type(v) == list:
                tokens.extend(
                    [t for t in v if t not in REPLACE_NEWS and t not in REPLACE_OLDS and t != EditSeqTokens.REPLACE_END]
                )
            else:
                if v not in REPLACE_NEWS and v not in REPLACE_OLDS and v != EditSeqTokens.REPLACE_END:
                    tokens.append(v)

        while len(edit_seq) > 0:
            checked = False
            while not checked:
                checked = True
                for t in tokens:
                    if edit_seq.startswith(t):
                        edit_seq = edit_seq[len(t) :]
                        if new_edit_seq.endswith(" ") and edit_seq.startswith(" "):
                            edit_seq = edit_seq[1:]
                        checked = False

            if len(edit_seq) > 0:
                new_edit_seq += edit_seq[0]
                edit_seq = edit_seq[1:]

        return new_edit_seq.strip()

    @staticmethod
    def decode_outputs(row, outputs, tokenizer):
        pred_edit_seqs = tokenizer.batch_decode(outputs, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        target_edit_seq = row["output"]

        target_edit_seq = EditSequenceDataEncoder.remove_special_tokens(target_edit_seq, tokenizer)

        for i in range(len(pred_edit_seqs)):
            pred_edit_seqs[i] = EditSequenceDataEncoder.remove_special_tokens(pred_edit_seqs[i], tokenizer)

        src = ""
        if "sourceChanges" in row["hunk"]:
            src = " ".join([c["line"] for c in row["hunk"]["sourceChanges"]])

        preds = []
        for p in pred_edit_seqs:
            applied_pred = apply_edit_sequence(src, p)

            if not applied_pred:
                preds.append("Invalid Prediction")
            else:
                preds.append(applied_pred.strip())

        return {
            "ID": row["ID"],
            "target": row["target_change"],
            "preds": preds,
            "target_es": target_edit_seq,
            "pred_es": pred_edit_seqs,
        }


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
            edit_sequence.append(
                (
                    [
                        EditSeqTokens.REPLACE_OLD,
                        source[source_start:source_end],
                        EditSeqTokens.REPLACE_NEW,
                        target[target_start:target_end],
                        EditSeqTokens.REPLACE_END,
                    ],
                    source_start,
                    source_end,
                    target_start,
                    target_end,
                )
            )
            replace_found = True

        else:
            # > 1 possible replace in the source, start appending tokens before the change to find a unique replace
            if index != 0:
                preceding_tokens = list(
                    filter(None, source[req_changes[index - 1][1] : req_changes[index - 1][2]].split(" "))
                )

                if len(preceding_tokens) > 0:
                    i = len(preceding_tokens) - 1
                    replace = preceding_tokens[i]
                    i -= 1

                    source_to_replace = (" " if source_start != source_end else "") + source[source_start:source_end]
                    while source.count(f"{replace}{source_to_replace}") > 1 and i >= 0:
                        replace = f"{preceding_tokens[i]} {replace}"
                        i -= 1

                    if source.count(f"{replace} {source[source_start:source_end]}") == 1:
                        edit_sequence.append(
                            (
                                [
                                    EditSeqTokens.REPLACE_KEEP_BEFORE_OLD,
                                    f"{replace}{source_to_replace}",
                                    EditSeqTokens.REPLACE_KEEP_BEFORE_NEW,
                                    f"{replace} {target[target_start:target_end]}",
                                    EditSeqTokens.REPLACE_END,
                                ],
                                req_changes[index - 1][1],
                                source_end,
                                req_changes[index - 1][3],
                                target_end,
                            )
                        )
                        replace_found = True

            # > 1 possible replace in the source, start appending tokens after the change to find a unique replace
            if not replace_found and index != len(req_changes) - 1:
                following_tokens = list(
                    filter(None, source[req_changes[index + 1][1] : req_changes[index + 1][2]].split(" "))
                )

                if len(following_tokens) > 0:
                    replace = following_tokens[0]
                    i = 1

                    source_to_replace = source[source_start:source_end] + (" " if source_start != source_end else "")
                    while source.count(f"{source_to_replace}{replace}") > 1 and i <= len(following_tokens) - 1:
                        replace = f"{replace} {following_tokens[i]}"
                        i += 1

                    if source.count(f"{source[source_start:source_end]} {replace}") == 1:
                        edit_sequence.append(
                            (
                                [
                                    EditSeqTokens.REPLACE_KEEP_AFTER_OLD,
                                    f"{source_to_replace}{replace}",
                                    EditSeqTokens.REPLACE_KEEP_AFTER_NEW,
                                    f"{target[target_start:target_end]} {replace}",
                                    EditSeqTokens.REPLACE_END,
                                ],
                                source_start,
                                req_changes[index - 1][2],
                                target_start,
                                req_changes[index - 1][4],
                            )
                        )
                        replace_found = True

            # > 1 possible replace in the source, start appending tokens before and after the change to find a unique replace
            if not replace_found and index != len(req_changes) - 1 and index != 0:
                preceding_tokens = list(
                    filter(None, source[req_changes[index - 1][1] : req_changes[index - 1][2]].split(" "))
                )
                following_tokens = list(
                    filter(None, source[req_changes[index + 1][1] : req_changes[index + 1][2]].split(" "))
                )

                if len(preceding_tokens) > 0 and len(following_tokens) > 0:
                    replace_before = preceding_tokens[-1]
                    replace_after = following_tokens[0]
                    i = 1

                    source_to_replace = (
                        (" " if source_start != source_end else "")
                        + source[source_start:source_end]
                        + (" " if source_start != source_end else "")
                    )
                    while source.count(f"{replace_before}{source_to_replace}{replace_after}") > 1:
                        if i < len(following_tokens):
                            replace_after = f"{replace_after} {following_tokens[i]}"
                        if i < len(preceding_tokens):
                            replace_before = f"{preceding_tokens[-1-i]} {replace_before}"
                        i += 1
                        if i >= len(following_tokens) and i >= len(preceding_tokens):
                            break

                    if source.count(f"{replace_before} {source[source_start:source_end]} {replace_after}") == 1:
                        edit_sequence.append(
                            (
                                [
                                    EditSeqTokens.REPLACE_KEEP_BEFORE_AFTER_OLD,
                                    f"{replace_before}{source_to_replace}{replace_after}",
                                    EditSeqTokens.REPLACE_KEEP_BEFORE_AFTER_NEW,
                                    f"{replace_before} {target[target_start:target_end]} {replace_after}",
                                    EditSeqTokens.REPLACE_END,
                                ],
                                req_changes[index - 1][1],
                                req_changes[index - 1][2],
                                req_changes[index - 1][3],
                                req_changes[index - 1][4],
                            )
                        )
                        replace_found = True

        if not replace_found:
            replace_source, replace_target = source[source_start:source_end], target[target_start:target_end]
            new_next_index, prev_index, to_be_removed = index, index, 0

            while not replace_found and (new_next_index < len(req_changes) - 2 or prev_index >= 1):
                if new_next_index < len(req_changes) - 2:
                    next_equal = req_changes[new_next_index + 1]
                    replace_source += source[next_equal[1] : next_equal[2]]
                    replace_target += target[next_equal[3] : next_equal[4]]

                    next_change = req_changes[new_next_index + 2]
                    replace_source += source[next_change[1] : next_change[2]]
                    replace_target += target[next_change[3] : next_change[4]]

                    source_end = next_change[2]
                    target_end = next_change[4]
                    new_next_index += 2

                    if source.count(replace_source) == 1:
                        replace_found = True

                if not replace_found and prev_index >= 1:
                    prev_equal = req_changes[prev_index - 1]
                    replace_source = source[prev_equal[1] : prev_equal[2]] + replace_source
                    replace_target = target[prev_equal[3] : prev_equal[4]] + replace_target

                    prev_change = req_changes[prev_index - 2]
                    replace_source = source[prev_change[1] : prev_change[2]] + replace_source
                    replace_target = target[prev_change[3] : prev_change[4]] + replace_target

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

                edit_sequence = edit_sequence[: len(edit_sequence) - count]
                edit_sequence.append(
                    (
                        [
                            EditSeqTokens.REPLACE_GROUP_OLD,
                            source[source_start:source_end],
                            EditSeqTokens.REPLACE_GROUP_NEW,
                            target[target_start:target_end],
                            EditSeqTokens.REPLACE_END,
                        ],
                        source_start,
                        source_end,
                        target_start,
                        target_end,
                    )
                )
                next_index = new_next_index

        all_replaces = all_replaces and replace_found

    i = 0
    while i < len(edit_sequence) - 1:
        curr_e = edit_sequence[i]
        next_e = edit_sequence[i + 1]

        while next_e and curr_e[2] > next_e[1]:
            curr_e = (
                [
                    EditSeqTokens.REPLACE_GROUP_OLD,
                    source[curr_e[1] : next_e[2]],
                    EditSeqTokens.REPLACE_GROUP_NEW,
                    target[curr_e[3] : next_e[4]],
                    EditSeqTokens.REPLACE_END,
                ],
                curr_e[1],
                next_e[2],
                curr_e[3],
                next_e[4],
            )

            if i + 1 < len(edit_sequence):
                del edit_sequence[i + 1]
            if i + 1 < len(edit_sequence):
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
            if source.count(new_s) == 1:
                s = new_s
            else:
                all_replaces = False

        if not t in target:
            new_t = add_padding_to_chars(t)
            if target.count(new_t) == 1:
                t = new_t
            else:
                all_replaces = False

        edit_sequence[i] = ([token1, s, token2, t, token3],)

    return " ".join([e1 for e0 in edit_sequence for e1 in e0[0]]), all_replaces


def substring_surrounded_by_spaces(full_string, start, end, change_type):
    is_equal = change_type == "equal"

    start_space = (
        len(full_string) == 0
        or start <= 0
        or start >= len(full_string)
        or (full_string[start].isspace() and is_equal)
        or (full_string[start - 1].isspace() and not is_equal)
    )

    end_space = (
        len(full_string) == 0
        or end >= len(full_string)
        or (full_string[end - 1].isspace() and is_equal)
        or (full_string[end].isspace() and not is_equal)
    )

    return start_space and end_space, start_space, end_space


def find_token_diffs(source, target):
    sm = difflib.SequenceMatcher(a=source, b=target)
    req_changes = sm.get_opcodes()
    final_changes = []

    index = 0
    while index < len(req_changes):
        change_type, source_start, source_end, target_start, target_end = req_changes[index]

        source_surrounded_by_spaces, source_start_space, source_end_space = substring_surrounded_by_spaces(
            source, source_start, source_end, change_type
        )
        target_surrounded_by_spaces, target_start_space, target_end_space = substring_surrounded_by_spaces(
            target, target_start, target_end, change_type
        )

        if index < len(req_changes) - 1:
            next_change = req_changes[index + 1]
        else:
            next_change = None

        if change_type == "equal":
            while source_start < source_end < len(source) and (
                not source_surrounded_by_spaces
                or (next_change and next_change[0] == "insert" and not target_surrounded_by_spaces)
            ):
                source_end -= 1
                target_end -= 1

                if next_change:
                    next_change = (next_change[0], next_change[1] - 1, next_change[2], next_change[3] - 1, next_change[4])

        else:
            check_source = True
            target_changed = False
            while check_source:
                while source_end < len(source) and not (
                    source_end_space
                    or (change_type == "insert" and target_surrounded_by_spaces and source_start == source_end)
                ):
                    source_end += 1
                    source_surrounded_by_spaces, source_start_space, source_end_space = substring_surrounded_by_spaces(
                        source, source_start, source_end, change_type
                    )

                    if change_type == "delete" and not target_changed:
                        target_end += 1
                        target_surrounded_by_spaces, target_start_space, target_end_space = substring_surrounded_by_spaces(
                            target, target_start, target_end, change_type
                        )

                    if next_change:
                        next_change = (
                            next_change[0],
                            source_end,
                            next_change[2],
                            target_end,
                            next_change[4],
                        )
                        if next_change[1] >= next_change[2]:
                            target_end = next_change[4]
                            (
                                target_surrounded_by_spaces,
                                target_start_space,
                                target_end_space,
                            ) = substring_surrounded_by_spaces(target, target_start, target_end, change_type)

                            req_changes.pop(index + 1)
                            if index < len(req_changes) - 1:
                                next_change = req_changes[index + 1]
                                next_change = (next_change[0], source_end, next_change[2], target_end, next_change[4])
                            else:
                                next_change = None
                check_source = False

                while target_start != target_end < len(target) and not (
                    target_end_space
                    or (change_type == "delete" and source_surrounded_by_spaces and target_start == target_end)
                ):
                    target_end += 1
                    target_surrounded_by_spaces, target_start_space, target_end_space = substring_surrounded_by_spaces(
                        target, target_start, target_end, change_type
                    )
                    target_changed = True

                    if change_type == "delete":
                        source_end += 1
                        source_surrounded_by_spaces, source_start_space, source_end_space = substring_surrounded_by_spaces(
                            source, source_start, source_end, change_type
                        )

                    if next_change:
                        next_change = (
                            next_change[0],
                            source_end,
                            next_change[2],
                            target_end,
                            next_change[4],
                        )
                        if next_change[3] >= next_change[4]:
                            source_end = next_change[2]
                            (
                                source_surrounded_by_spaces,
                                source_start_space,
                                source_end_space,
                            ) = substring_surrounded_by_spaces(source, source_start, source_end, change_type)
                            check_source = True

                            req_changes.pop(index + 1)
                            if index < len(req_changes) - 1:
                                next_change = req_changes[index + 1]
                                next_change = (next_change[0], source_end, next_change[2], target_end, next_change[4])
                            else:
                                next_change = None

        append_curr = True
        if next_change:
            if change_type == "equal" and source_end - source_start != target_end - target_start:
                append_curr = False
                if next_change:
                    req_changes[index + 1] = (next_change[0], source_start, next_change[2], target_start, next_change[4])
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
        if curr_e[1] == curr_e[2] and target[curr_e[4] - 1] == " ":
            curr_e = (curr_e[0], curr_e[1], next_e[2], curr_e[3], next_e[4])
            del final_changes[i + 1]
            next_e = None

        if i < len(final_changes) - 1:
            next_e = final_changes[i + 1]

        while next_e and (curr_e[0] == next_e[0] == "equal" or (curr_e[0] != "equal" and next_e[0] != "equal")):
            curr_e = ("equal" if curr_e[0] == "equal" else "replace", curr_e[1], next_e[2], curr_e[3], next_e[4])

            if i + 1 < len(final_changes):
                del final_changes[i + 1]
            if i + 1 < len(final_changes):
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
        if orig is None or new is None or original_code[: last_index + len(orig) - 1].count(orig) != 1:
            return None

        last_index = original_code.index(orig)
        original_code = original_code.replace(orig, new, 1)

    return original_code


def get_replace_pairs(edit_seq):
    if EditSeqTokens.REPLACE_END not in edit_seq:
        return None

    replaces = [r for r in edit_seq.split(f" {EditSeqTokens.REPLACE_END}") if r]
    pairs = []

    for r in replaces:
        orig, new = None, None
        old_found = False
        for old in REPLACE_OLDS:
            if old in r:
                r = re.sub(f"\s*{re.escape(old)} ", "", r)
                old_found = True
                break

        if not old_found:
            return None

        for new in REPLACE_NEWS:
            if new in r:
                blocks = re.split(f" ?{re.escape(new)} ?", r)
                if len(blocks) == 2:
                    orig, new = blocks[0], blocks[1]
                break

        if not orig or not new:
            return None

        pairs.append((orig, new))

    return pairs


def get_default_edit_sequence(broken, repaired):
    return " ".join([EditSeqTokens.REPLACE_OLD, broken, EditSeqTokens.REPLACE_NEW, repaired, EditSeqTokens.REPLACE_END])
