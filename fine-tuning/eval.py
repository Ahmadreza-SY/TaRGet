from pathlib import Path
import torch.distributed as dist
import logging
import bleu as bleu_scoring
from encoders import *
import json
import pandas as pd
from joblib import Parallel, delayed
import git
from tqdm import tqdm
from datetime import datetime
from torch.nn.parallel import DistributedDataParallel
from torch.nn import CrossEntropyLoss
import maven_parser as mvnp
import git_api as ghapi
from common_utils import decompose_full_method_name
from utils import create_loader, save_stats


def test(gpu, args):
    logger = logging.getLogger(args.pname)
    if args.rank == 0:
        logger.info("***** Testing *****")
    best_checkpoint_path = args.output_dir / f"checkpoint-best"
    model = args.model_class.from_pretrained(best_checkpoint_path)
    model.resize_token_embeddings(len(args.tokenizer))
    model = model.to(gpu)
    model = DistributedDataParallel(model, device_ids=[gpu], output_device=gpu, find_unused_parameters=True)

    if args.rank == 0:
        logger.info(f"    Testing with best checkpoint on Valid set")
    bleu_score, em, sr, _ = eval(model, "valid", args, best_checkpoint_path)

    if args.rank == 0:
        logger.info(f"    Testing with best checkpoint on Test set")
    bleu_score, em, sr, test_loss = eval(model, "test", args, args.output_dir)
    args.stats["test_results"] = {"bleu": bleu_score, "em": em, "sr": sr, "loss": test_loss}

    save_stats(args)


def eval(model, split, args, save_dir):
    logger = logging.getLogger(args.pname)
    if split == "valid":
        dataset = args.valid_dataset
    elif split == "test":
        dataset = args.test_dataset

    start = datetime.now()

    tokenizer = args.tokenizer
    model.eval()
    model_module = model.module if hasattr(model, "module") else model
    loader = create_loader(dataset, args, True)

    global_preds = [None for _ in range(args.world_size)]
    global_targets = [None for _ in range(args.world_size)]
    global_ids = [None for _ in range(args.world_size)]
    global_loss = [None for _ in range(args.world_size)]

    local_preds = []
    local_targets = []
    local_ids = []
    local_loss = []

    for _, data in enumerate(loader, 1):
        source_ids, source_mask, target_ids, data_ids = tuple(item for item in data)

        source_ids, source_mask, target_ids = source_ids.to(args.gpu), source_mask.to(args.gpu), target_ids.to(args.gpu)
        outputs = model_module(input_ids=source_ids, attention_mask=source_mask, labels=target_ids, output_attentions=False)
        lm_logits = outputs.logits
        lm_loss_fct = CrossEntropyLoss(ignore_index=model_module.config.pad_token_id, label_smoothing=args.label_smoothing)
        loss = lm_loss_fct(lm_logits.view(-1, lm_logits.size(-1)), target_ids.view(-1))
        local_loss.append(loss.item())

        if args.eval_full_beam:
            outputs = model_module.generate(
                input_ids=source_ids,
                attention_mask=source_mask,
                num_beams=args.beam_size,
                max_length=args.max_seq,
                use_cache=True,
                early_stopping=True,
                num_return_sequences=args.beam_size,
            )
            # For prediction certainty
            # outputs.scores[0].view(-1, args.beam_size, model_module.config.vocab_size).shape
            curr_batch_size = target_ids.shape[0]
            batch_preds = outputs.view(curr_batch_size, args.beam_size, -1).cpu().tolist()
            for i, beam_preds in enumerate(batch_preds):
                for pred in beam_preds:
                    local_preds.append(pred)
                    local_targets.append(target_ids[i])
                    local_ids.append(data_ids[i])
        else:
            pred_ids = model_module.generate(
                input_ids=source_ids,
                attention_mask=source_mask,
                num_beams=args.beam_size,
                max_length=args.max_seq,
                use_cache=True,
                early_stopping=True,
            )
            local_preds.extend(pred_ids.cpu().tolist())
            local_targets.extend(target_ids)
            local_ids.extend(data_ids)

    dist.gather_object(local_preds, global_preds if args.rank == 0 else None, dst=0)
    dist.gather_object(local_targets, global_targets if args.rank == 0 else None, dst=0)
    dist.gather_object(local_ids, global_ids if args.rank == 0 else None, dst=0)
    dist.gather_object(local_loss, global_loss if args.rank == 0 else None, dst=0)
    if args.rank == 0:
        all_targets = [item for sub in global_targets for item in sub]
        all_preds = [item for sub in global_preds for item in sub]
        all_ids = [item for sub in global_ids for item in sub]
        all_loss = [item for sub in global_loss for item in sub]
        logger.debug(f"    Gathered {len(all_preds)} , {len(all_targets)} targets and predictions")

        def decode(tokens):
            return tokenizer.decode(tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False)

        target_codes = Parallel(n_jobs=-1)(delayed(decode)(tokens) for tokens in all_targets)
        pred_codes = Parallel(n_jobs=-1)(delayed(decode)(tokens) for tokens in all_preds)
        all_bleus = compute_single_bleus(target_codes, pred_codes)

        pred_df = pd.DataFrame(
            {
                "id": all_ids,
                "pred": pred_codes,
                "target": target_codes,
                "rank": list(range(1, args.beam_size + 1)) * len(dataset),
                "bleu": all_bleus,
            }
        )

        bleu_score, em = compute_scores(target_codes, pred_codes, all_ids)
        avg_loss = round(sum(all_loss) / len(all_loss), 3)
        logger.info(f"    * BLEU: {bleu_score} ; EM: {em} ; Loss: {avg_loss} ; Eval took: {datetime.now() - start}")

        success_rate = None
        if split == "test":
            verdicts = apply_and_run_preds(pred_df, args.output_dir, split)
            pred_df["verdict"] = [v.to_dict() for v in verdicts]
            success_cnt = sum([1 if v.status == mvnp.TestVerdict.SUCCESS else 0 for v in verdicts])
            success_rate = round(100 * success_cnt / len(verdicts), 1)
            logger.info(f"    * SR: {success_rate}")

        save_dir.mkdir(parents=True, exist_ok=True)
        pred_df.to_json(save_dir / f"{split}_predictions.json", orient="records", indent=2)
        scores = [bleu_score, em, success_rate, avg_loss]
    else:
        scores = [None, None, None, None]

    dist.broadcast_object_list(scores, src=0)
    bleu_score, em, sr, loss = scores[0], scores[1], scores[2], scores[3]
    return bleu_score, em, sr, loss


def compute_single_bleus(targets, preds):
    bleus = []
    for target, pred in zip(targets, preds):
        if len(target) == 0:
            bleus.append(100.0 if len(pred) == 0 else 0.0)
            continue
        if len(pred) == 0:
            bleus.append(0.0)
            continue
        bleu = bleu_scoring._bleu([target], [pred])
        bleus.append(bleu)
    return bleus


def compute_scores(targets, preds, ids):
    df = pd.DataFrame({"target": targets, "pred": preds, "id": ids})
    eval_size = df["id"].nunique()
    em_size = 0
    best_preds = []
    best_targets = []
    for _, beam_outputs in df.groupby("id"):
        best_pred = beam_outputs.iloc[0]["pred"]
        for _, output in beam_outputs.iterrows():
            if output["pred"] == output["target"]:
                em_size += 1
                best_pred = output["pred"]
                break
        best_preds.append(best_pred)
        best_targets.append(beam_outputs.iloc[0]["target"])

    em = round(em_size / eval_size * 100, 2)
    bleu_score = bleu_scoring._bleu(best_targets, best_preds)

    return bleu_score, em


def apply_and_run_preds(pred_df, output_dir, split):
    test_ds = {row["ID"]: row for row in json.loads((output_dir / "splits" / f"{split}.json").read_text())}

    test_pairs = [(pred, test_ds[pred["id"]]) for _, pred in pred_df.iterrows()]
    test_pairs.sort(key=lambda a: a[1]["aCommit"])

    git_dir = output_dir / "git"
    git_dir.mkdir(parents=True, exist_ok=True)

    verdicts = []
    curr_commit = None
    curr_repo = None
    worktree = None

    for pred, test in tqdm(test_pairs, desc="Executing test patches"):
        repo_name = test["ID"].split(":")[0]

        commit = test["aCommit"]
        if commit != curr_commit or repo_name != curr_repo:
            if curr_repo:
                ghapi.cleanup_worktrees(curr_repo, git_dir / curr_repo)

            worktree_path = ghapi.copy_commit_code(repo_name, commit, git_dir / repo_name)
            curr_repo = repo_name
            curr_commit = commit

            worktree = git.Repo(worktree_path)

        test_rel_path = Path(test["aPath"])
        test_file = worktree_path / test_rel_path

        with open(test_file, "r") as orig_file:
            contents = orig_file.read()

        if len(test["hunk"]["targetChanges"]) > 0:
            contents = contents.split("\n")
            target_line = test["hunk"]["targetChanges"][0]["lineNo"] - 1
            for tc in test["hunk"]["targetChanges"][::-1]:
                del contents[tc["lineNo"] - 1]
            contents.insert(target_line, pred["pred"])
            contents = "\n".join(contents)
        else:
            test_method = test["bSource"]["code"].split("\n")
            start_line = test["bSource"]["startLine"]
            target_line = test["hunk"]["sourceChanges"][0]["lineNo"] - start_line
            for tc in test["hunk"]["sourceChanges"][::-1]:
                del test_method[tc["lineNo"] - start_line]
            test_method.insert(target_line, pred["pred"])
            contents.replace(test["aSource"]["code"], "\n".join(test_method))

        with open(test_file, "w") as orig_file:
            orig_file.write(contents)

        _, class_name, test_short_name = decompose_full_method_name(test["name"])
        log_path = (
            output_dir
            / "testLogs"
            / test["aCommit"]
            / class_name
            / test_short_name
            / test_rel_path.parent
            / str(pred["rank"])
        )
        verdict = mvnp.compile_and_run_test(worktree_path, test_rel_path, test_short_name, log_path)
        verdicts.append(verdict)

        worktree.git.reset("--hard")

    if curr_repo:
        ghapi.cleanup_worktrees(curr_repo, git_dir / curr_repo)

    # shutil.rmtree(base_output_dir / "testLogs")
    # shutil.rmtree(git_dir)

    return verdicts
