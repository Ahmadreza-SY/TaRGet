import json
from pathlib import Path
from encoders.preprocessing.textDiff import get_hunk_diffs
from diff_match_patch import diff_match_patch as dmp
from tqdm import tqdm
from encoders.repositories.changeRepo import ChangeRepository
from encoders.abstractEncoder import AbstractDataEncoder
import argparse

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--dataset_dir", required=True, type=str)
    parser.add_argument("-o", "--output_dir", required=True, type=str)
    args = parser.parse_args()

    ade = AbstractDataEncoder(None)
    change_repo = ChangeRepository(args=args)

    with open(f'{args.output_dir}/splits/test.json', 'r') as f:
        test_set = json.load(f)

    preds = []
    count = 0
    for t in tqdm(test_set):
        broken = ade.get_broken_code(t)
        target = ade.get_repaired_code(t)
        prediction = ""

        sut_changes = change_repo.get_commit_changes(t["ID"].split(":")[0], t["aCommit"])

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
                            next_diff = diffs[i+1]

                        if curr_diff[0] == dmp.DIFF_DELETE:
                            rem = curr_diff[1]
                            rep = ""
                            if next_diff and next_diff[0] == dmp.DIFF_INSERT:
                                i += 1
                                rep = next_diff[1]

                            all_diff_pairs.append((rem, rep))

                        i += 1

        for d in all_diff_pairs:
            if broken.count(d[0]) == 1:
                broken = broken.replace(d[0], d[1])

        preds.append({"ID": t["ID"],
                "target": target,
                "preds": [broken]})

    Path(f'{args.output_dir}/sutcopy/').mkdir(parents=True, exist_ok=True)

    with open(f'{args.output_dir}/sutcopy/test_predictions.json', 'w') as f:
        json.dump(preds, f, indent=4)