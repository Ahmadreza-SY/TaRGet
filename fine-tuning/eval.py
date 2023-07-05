import torch.distributed as dist
import logging
from encoders import *
import pandas as pd
from joblib import Parallel, delayed
from datetime import datetime
from torch.nn.parallel import DistributedDataParallel
from torch.nn import CrossEntropyLoss
from utils import create_loader, save_stats
from nltk.translate.bleu_score import corpus_bleu, sentence_bleu


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
    bleu_score, em, _ = eval(model, "valid", args, best_checkpoint_path)

    if args.rank == 0:
        logger.info(f"    Testing with best checkpoint on Test set")
    bleu_score, em, test_loss = eval(model, "test", args, args.output_dir)
    args.stats["test_results"] = {"bleu": bleu_score, "em": em, "loss": test_loss}

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
        target_ids = target_ids.to("cpu")

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
            outputs = outputs.view(curr_batch_size, args.beam_size, -1).cpu().tolist()
            for i, beam_preds in enumerate(outputs):
                for pred in beam_preds:
                    local_preds.append(pred)
                    local_targets.append(target_ids[i])
                    local_ids.append(data_ids[i])
        else:
            pred_ids = (
                model_module.generate(
                    input_ids=source_ids,
                    attention_mask=source_mask,
                    num_beams=args.beam_size,
                    max_length=args.max_seq,
                    use_cache=True,
                    early_stopping=True,
                )
                .cpu()
                .tolist()
            )
            local_preds.extend(pred_ids)
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

        ranks = list(range(1, args.beam_size + 1)) if args.eval_full_beam else [1]
        pred_df = pd.DataFrame(
            {
                "id": all_ids,
                "pred": pred_codes,
                "target": target_codes,
                "rank": ranks * len(dataset),
                "bleu": all_bleus,
            }
        )

        bleu_score, em = compute_scores(target_codes, pred_codes, all_ids)
        avg_loss = round(sum(all_loss) / len(all_loss), 3)
        logger.info(f"    * BLEU: {bleu_score} ; EM: {em} ; Loss: {avg_loss} ; Eval took: {datetime.now() - start}")
        save_dir.mkdir(parents=True, exist_ok=True)
        pred_df.to_json(save_dir / f"{split}_predictions.json", orient="records", indent=2)

        scores = [bleu_score, em, avg_loss]
    else:
        scores = [None, None, None]

    dist.broadcast_object_list(scores, src=0)
    bleu_score, em, loss = scores[0], scores[1], scores[2]
    return bleu_score, em, loss


def compute_single_bleus(targets, preds):
    bleus = []
    for target, pred in zip(targets, preds):
        if len(target) == 0:
            bleus.append(100.0 if len(pred) == 0 else 0.0)
            continue
        if len(pred) == 0:
            bleus.append(0.0)
            continue
        bleu = compute_bleu_score([target], [pred])
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
    bleu_score = compute_bleu_score(best_targets, best_preds)

    return bleu_score, em


def compute_bleu_score(targets, preds):
    if len(targets) != len(preds):
        raise Exception(f"Targets and preds size mismatch in compute_bleu_score: {len(targets)} != {len(preds)}")

    simple_tokenize = lambda text: text.strip().split()
    format_score = lambda score: round(100 * score, 2)

    if len(targets) == 1:
        reference = [simple_tokenize(targets[0])]
        candidate = simple_tokenize(preds[0])
        return format_score(sentence_bleu(reference, candidate))

    references = [[simple_tokenize(target)] for target in targets]
    candidates = [simple_tokenize(pred) for pred in preds]
    return format_score(corpus_bleu(references, candidates))
