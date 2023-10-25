

class AllHunksDataEncoder(AbstractDataEncoder):
    def create_hunk_document(self, hunk):
        diffs = get_hunk_diffs(hunk)
        annotated_body = []
        for type, text in diffs:
            text = text.strip()
            if type == dmp.DIFF_EQUAL:
                annotated_body.append(text)
            elif type == dmp.DIFF_DELETE:
                annotated_body.extend([Tokens.DELETE, text, Tokens.DELETE_END])
            elif type == dmp.DIFF_INSERT:
                annotated_body.extend([Tokens.ADD, text, Tokens.ADD_END])
        annotated_doc = "".join([Tokens.HUNK] + annotated_body + [Tokens.HUNK_END])

        return annotated_doc

    def hunks_count(self, changes):
        return sum(len(c["hunks"]) for c in changes)

    def preprocess_all_class_changes(self, changes, stats):
        preprocessors = [
            format_sut_changes,
            remove_whitespace_hunks,
            remove_empty_hunks,
        ]
        for preprocess in preprocessors:
            b_len = self.hunks_count(changes)
            changes = preprocess(changes)
            a_len = self.hunks_count(changes)
            stats["hunk_pp"][preprocess.__name__] = stats["hunk_pp"].get(preprocess.__name__, 0) + (b_len - a_len)
        for change in changes:
            for hunk in change["hunks"]:
                annotated_doc = self.create_hunk_document(hunk)
                hunk["annotated_doc"] = annotated_doc
                hunk["annotated_doc_seq"] = self.tokenizer.encode(annotated_doc)
        return changes

    def get_empty_changes_reason(self, changes, changes_wo_t, changes_pp):
        if len(changes) == 0:
            return "Originally Empty"
        elif len(changes_wo_t) == 0:
            return "All Test Source"
        elif len(changes_pp) == 0:
            if len(changes_wo_t) == len(changes):
                return "Preproccessing"
            else:
                return "Combination of Both"

    def log_stats(self, ds, stats):
        # Empty change stats
        stats_cnt = {}
        empty_chn = stats["empty_chn"]
        for _, row in ds.iterrows():
            key = f"{row['project']}/{row['aCommit']}"
            if key in empty_chn:
                reason = empty_chn[key]
                stats_cnt.setdefault(reason, 0)
                stats_cnt[reason] += 1
        for k, v in stats_cnt.items():
            self.log(f"Got {v} empty changes due to {k}")

        # Hunks preprocessing stats
        total_hunks = stats["hunks"] + sum(stats["hunk_pp"].values())
        for k, v in stats["hunk_pp"].items():
            if v > 0:
                self.log(f"{k} removed {v} ({round(100*v/total_hunks, 1)}%) hunks from SUT changes")
                total_hunks -= v
        self.log(f"Total SUT hunks after preprocessing: {total_hunks}")

    def get_all_class_changes(self, project, a_commit, changes_cache, stats):
        key = f"{project}/{a_commit}"

        if key not in changes_cache:
            ds_path = Path(self.args.dataset_dir)
            if project not in self.args.dataset_dir:
                ds_path = ds_path / project
            changes_path = list(ds_path.rglob("sut_class_changes.json"))
            if len(changes_path) == 1:
                changes = json.loads(changes_path[0].read_text())
                for commit_changes in changes:
                    commit_changes_wo_t = [c for c in commit_changes["changes"] if not c["is_test_source"]]
                    commit_changes_pp = self.preprocess_all_class_changes(commit_changes_wo_t, stats)
                    current_key = f"{project}/{commit_changes['aCommit']}"
                    changes_cache[current_key] = commit_changes_pp
                    stats["hunks"] += self.hunks_count(commit_changes_pp)
                    if len(commit_changes_pp) == 0:
                        stats["empty_chn"][current_key] = self.get_empty_changes_reason(
                            commit_changes["changes"], commit_changes_wo_t, commit_changes_pp
                        )

        if key not in changes_cache:
            stats["empty_chn"][key] = "Not Found"
            changes_cache[key] = []

        return changes_cache.get(key, [])

    def read_data(self):
        ds = super().read_data()
        self.log(f"Reading and preprocessing all class changes")
        changes_cache = {}
        stats = {"empty_chn": {}, "hunk_pp": {}, "hunks": 0}
        all_class_changes = []
        for _, row in ds.iterrows():
            changes = self.get_all_class_changes(row["project"], row["aCommit"], changes_cache, stats)
            all_class_changes.append(changes)
        ds["allClassChanges"] = all_class_changes
        self.log_stats(ds, stats)
        return ds

    def create_changed_document(self, row, hunk):
        doc = hunk["doc"]
        return {"doc": doc, "annotated_doc": hunk["annotated_doc"], "annotated_doc_seq": hunk["annotated_doc_seq"]}

    def get_changed_documents(self, row):
        changes = row["allClassChanges"]
        change_docs = []
        change_repeat = {}
        for change in changes:
            for hunk in change["hunks"]:
                doc = hunk["doc"]
                change_docs.append(self.create_changed_document(row, hunk))
                if doc not in change_repeat:
                    change_repeat[doc] = 0
                change_repeat[doc] = change_repeat[doc] + 1
        for change_doc in change_docs:
            change_doc["repeat"] = change_repeat[change_doc["doc"]]
        return change_docs

    def get_sort_key(self, changed_doc):
        return (-changed_doc["tfidf_breakage"], -changed_doc["repeat"], -changed_doc["tfidf_testsrc"])


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


class ASTElementsDataEncoder(AllHunksDataEncoder):
    def create_changed_document(self, row, hunk):
        changed_doc = super().create_changed_document(row, hunk)
        changed_doc["equal_ast_elements"] = 0
        changed_doc["similar_ast_elements"] = 0
        if "sourceElements" not in row["hunk"]:
            return changed_doc
        for t_e in row["hunk"]["sourceElements"]:
            for sut_e in hunk["sourceElements"]:
                if t_e["value"] == sut_e["value"]:
                    if t_e["type"] == sut_e["type"]:
                        changed_doc["equal_ast_elements"] += 1
                    else:
                        changed_doc["similar_ast_elements"] += 1
        return changed_doc

    def get_sort_key(self, changed_doc):
        return (
            -changed_doc["equal_ast_elements"],
            -changed_doc["similar_ast_elements"],
            -changed_doc["tfidf_breakage"],
            -changed_doc["repeat"],
            -changed_doc["tfidf_testsrc"],
        )
