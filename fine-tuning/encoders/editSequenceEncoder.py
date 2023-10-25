from encoders.preprocessing.codeFormatter import add_padding_to_chars
from encoders.preprocessing.editSequence import build_edit_sequence, apply_edit_sequence, get_replace_pairs
from encoders.abstractEncoder import Tokens


class EditSeqTokens(Tokens):
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


class EditSequenceDataEncoder(AllHunksDataEncoder):
    def get_special_tokens_class(self):
        return EditSeqTokens

    def create_output(self, row):
        repaired_code = ""
        output, success = build_edit_sequence(row.bSource["code"], row.aSource["code"])
        if success:
            repaired_code = output

        return repaired_code

    def create_inputs_and_outputs(self, ds):
        ds = super(EditSequenceDataEncoder, self).create_inputs_and_outputs(ds)
        num_without_output = len(ds[ds["output"].str.len() == 0].index)
        self.log(
            f"Removing {num_without_output} cases ({round(100 * num_without_output / len(ds.index), 2)} %) where edit sequence output could not be generated"
        )
        ds = ds[ds["output"].str.len() > 0].reset_index(drop=True)

        return ds

    @staticmethod
    def decode_outputs(row, outputs, tokenizer):
        pred_edit_seqs = tokenizer.batch_decode(outputs, skip_special_tokens=False, clean_up_tokenization_spaces=False)
        target_edit_seq = tokenizer.decode(
            tokenizer.encode(row["output"]), skip_special_tokens=False, clean_up_tokenization_spaces=False
        )

        if target_edit_seq.endswith(" </s>"):
            target_edit_seq = target_edit_seq[:-5]

        for i in range(len(pred_edit_seqs)):
            if pred_edit_seqs[i].endswith(" </s>"):
                pred_edit_seqs[i] = pred_edit_seqs[i][:-5]

        pred_edit_pairs = [get_replace_pairs(es) for es in pred_edit_seqs]
        target_edit_pairs = get_replace_pairs(target_edit_seq)

        preds, targets = [], []

        src, target = row["bSource"]["code"], add_padding_to_chars(row["aSource"]["code"])

        for i in range(len(pred_edit_pairs)):
            curr_pred_pairs = pred_edit_pairs[i]

            applied_pred = apply_edit_sequence(src, pred_edit_seqs[i], curr_pred_pairs)

            if not applied_pred:
                preds.append("Invalid")
            else:
                start = min([applied_pred.index(n) for _, n in curr_pred_pairs])
                end = max([applied_pred.index(n) + len(n) for _, n in curr_pred_pairs])

                start = [0].extend([i + 1 for i, char in enumerate(applied_pred) if i < start and char == ";"])[-1]
                end = [-1].extend([i + 1 for i, char in reversed(list(enumerate(applied_pred))) if i > end and char == ";"])[
                    -1
                ]

                preds.append(applied_pred[start:end])

        if not target_edit_pairs:
            target = "Invalid"
        else:
            edit_start = min([target.index(n) for _, n in target_edit_pairs])
            edit_end = max([target.index(n) + len(n) for _, n in target_edit_pairs])

            start = [0]
            start.extend([i + 1 for i, char in enumerate(target) if i < edit_start and char == ";"])
            start = start[-1]
            end = [-1]
            end.extend([i + 1 for i, char in reversed(list(enumerate(target))) if i > edit_end and char == ";"])
            end = end[-1]

            target = target[start : end + 1]

        return {"ID": row["ID"], "target": target, "preds": preds, "target_es": target_edit_seq, "pred_es": pred_edit_seqs}
