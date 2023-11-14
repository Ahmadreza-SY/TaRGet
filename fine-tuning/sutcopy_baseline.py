import json
from pathlib import Path
from encoders.preprocessing.textDiff import get_hunk_diffs
from diff_match_patch import diff_match_patch as dmp
from tqdm import tqdm

output_dir = "../outputeds"
data_dir = "../data/data-candidates-v3"

def get_broken_code(sample):
    broken_code = ""
    if "sourceChanges" in sample["hunk"] and len(sample["hunk"]["sourceChanges"]) > 0:
        broken_code = " ".join([c["line"] for c in sample["hunk"]["sourceChanges"]])
    return broken_code


def get_repaired_code(sample):
    repaired_code = ""
    if "targetChanges" in sample["hunk"] and len(sample["hunk"]["targetChanges"]) > 0:
        repaired_code = " ".join([c["line"] for c in sample["hunk"]["targetChanges"]])
    return repaired_code


with open(f'{output_dir}/splits/test.json', 'r') as f:
    test_set = json.load(f)

preds = []
count = 0
for t in tqdm(test_set):
    count += 1
    if count > 20:
        break
    broken = get_broken_code(t)
    target = get_repaired_code(t)
    prediction = ""

    sut_change_file = Path(f'{data_dir}/{t["ID"].split(":")[0]}/codeMining/sut_class_changes.json')

    if not sut_change_file.is_file():
        preds.append({"ID": t["ID"],
            "target": target,
            "preds": [""]})
        continue

    with open(sut_change_file, 'r') as f:
        sut_changes = [c for c in json.load(f) if c["aCommit"] == t["aCommit"] and c["bCommit"] == t["bCommit"]]

    if len(sut_changes) != 1:
        preds.append({"ID": t["ID"],
            "target": target,
            "preds": [""]})
        continue

    change = sut_changes[0]

    all_diff_pairs = []
    for c in change["changes"]:
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
        if d[0] in broken:
            broken = broken.replace(d[0], d[1])

    preds.append({"ID": t["ID"],
            "target": target,
            "preds": [broken]})

Path(f'{output_dir}/sutcopy/').mkdir(parents=True, exist_ok=True)

with open(f'{output_dir}/sutcopy/test_predictions.json', 'w') as f:
    json.dump(preds, f, indent=4)