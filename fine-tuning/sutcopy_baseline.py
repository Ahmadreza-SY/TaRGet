import json
from pathlib import Path
from encoders.preprocessing.textDiff import get_hunk_diffs
from diff_match_patch import diff_match_patch as dmp
from tqdm import tqdm
from encoders.repositories.changeRepo import ChangeRepository
from encoders.abstractEncoder import AbstractDataEncoder
import argparse
import pandas as pd
from eval import compute_scores
from datetime import datetime

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--test_file", required=True, type=str)
    parser.add_argument("-d", "--dataset_dir", required=True, type=str)
    parser.add_argument("-o", "--output_dir", required=True, type=str)
    args = parser.parse_args()

    ade = AbstractDataEncoder(None)
    change_repo = ChangeRepository(args=args)

    with open(args.test_file, "r") as f:
        test_set = json.load(f)

    start = datetime.now()
    preds = []
    count = 0
    for t in tqdm(test_set, desc="Applying SUTCopy to test set"):
        broken = ade.get_broken_code(t)
        target = ade.get_repaired_code(t)

        sut_changes = change_repo.get_commit_changes(t["project"], t["aCommit"])

        all_diff_pairs = []
        for c in sut_changes:
            for h in c["hunks"]:
                diffs = get_hunk_diffs(h)

                if len(diffs) > 0:
                    prev_type = 0
                    i = 0
                    while i < len(diffs):
                        curr_diff = diffs[i]
                        next_diff = None
                        if i < len(diffs) - 1:
                            next_diff = diffs[i + 1]

                        if curr_diff[0] == dmp.DIFF_DELETE:
                            rem = curr_diff[1]
                            rep = ""
                            if next_diff and next_diff[0] == dmp.DIFF_INSERT:
                                i += 1
                                rep = next_diff[1]

                            all_diff_pairs.append((rem, rep))

                        i += 1

        all_diff_pairs = sorted(all_diff_pairs, key=lambda p: len(p[0]), reverse=True)
        for d in all_diff_pairs:
            if broken.count(d[0]) == 1:
                broken = broken.replace(d[0], d[1])

        preds.append({"ID": t["ID"], "target": target, "preds": [broken]})

    args.output_dir = Path(args.output_dir)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    pred_df = pd.DataFrame(preds)
    bleu_score, code_bleu_score, em = compute_scores(pred_df)
    print(f"* BLEU: {bleu_score} ; CodeBLEU: {code_bleu_score} ; EM: {em} ; Eval took: {datetime.now() - start}")
    stats = {"testset_size": len(test_set), "test_results": {"bleu": bleu_score, "code_bleu": code_bleu_score, "em": em}}

    (args.output_dir / "stats.json").write_text(json.dumps(stats, indent=2, sort_keys=False))
    pred_df.to_json(args.output_dir / "test_predictions.json", orient="records", indent=2)
