from encoders.preprocessing.codeFormatter import add_padding_to_chars
from encoders.preprocessing.editSequence import build_edit_sequence, apply_edit_sequence, REPLACE_OLDS, REPLACE_NEWS
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


class EditSequenceDataEncoder(WordLevelDataEncoder):
    def get_special_tokens_class(self):
        return EditSeqTokens

    def create_output(self, row):
        repaired_code = ""
        output, success = build_edit_sequence(self.get_broken_code(row), self.get_repaired_code(row))
        if success:
            repaired_code = output

        return repaired_code

    def get_target_change(self, row):
        target_change = super(EditSequenceDataEncoder, self).create_output(row)
        return target_change.strip()

    def create_inputs_and_outputs(self, ds):
        ds = super(EditSequenceDataEncoder, self).create_inputs_and_outputs(ds)
        ds["target_change"] = ds.apply(lambda r: self.get_target_change(r), axis=1)
        num_without_output = len(ds[ds["output"].str.len() == 0].index)
        self.log(
            f"Removing {num_without_output} cases ({round(100 * num_without_output / len(ds.index), 2)} %) where edit sequence output could not be generated"
        )
        ds = ds[ds["output"].str.len() > 0].reset_index(drop=True)

        padded_targets = ds.apply(lambda r: self.get_repaired_code(r), axis=1)
        applied_seqs = ds.apply(lambda r: apply_edit_sequence(self.get_broken_code(r), r["output"]), axis=1)
        applied_seqs = applied_seqs.apply(lambda r: add_padding_to_chars(r) if r else None)
        applied_successes = padded_targets == applied_seqs
        applied_failure_count = len(applied_successes) - applied_successes.sum()
        self.log(
            f"{applied_failure_count} cases ({round(100 * applied_failure_count / len(applied_successes), 2)} %) where the edit sequence was not successfully applied"
        )

        return ds

    @staticmethod
    def remove_special_tokens(edit_seq, tokenizer):
        new_edit_seq = ""
        tokens = []
        for _, v in tokenizer.special_tokens_map.items():
            if type(v) == list:
                tokens.extend([t for t in v if t not in REPLACE_NEWS and t not in REPLACE_OLDS and t != Tokens.REPLACE_END])
            else:
                if v not in REPLACE_NEWS and v not in REPLACE_OLDS and v != Tokens.REPLACE_END:
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
