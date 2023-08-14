import torch.cuda
import torch.distributed as dist
import logging
from encoders import *
import pandas as pd
from datetime import datetime
from torch.nn.parallel import DistributedDataParallel
from torch.nn import CrossEntropyLoss
from utils import create_loader, save_stats
from nltk.translate.bleu_score import corpus_bleu, SmoothingFunction
from CodeBLEU.code_bleu import calc_code_bleu
import math


def test(gpu, args):
    logger = logging.getLogger(args.pname)
    if args.rank == 0:
        logger.info("***** Testing *****")
    best_checkpoint_path = args.output_dir / f"checkpoint-best"
    model = args.model_class.from_pretrained(best_checkpoint_path)
    args.tokenizer = args.model_tokenizer_class.from_pretrained(best_checkpoint_path)
    model.resize_token_embeddings(len(args.tokenizer))
    model = model.to(gpu)
    model = DistributedDataParallel(model, device_ids=[gpu], output_device=gpu, find_unused_parameters=True)

    if args.rank == 0:
        logger.info(f"Testing with best checkpoint on Valid set with size {len(args.valid_dataset)}")
    bleu_score, code_bleu_score, em, _ = eval(model, "valid", args, best_checkpoint_path)

    if args.rank == 0:
        logger.info(f"Testing with best checkpoint on Test set set with size {len(args.test_dataset)}")
    bleu_score, code_bleu_score, em, test_loss = eval(model, "test", args, args.output_dir)
    args.stats["test_results"] = {"bleu": bleu_score, "code_bleu": code_bleu_score, "em": em, "loss": test_loss}

    save_stats(args)

def get_predictions(loader, model_module, global_loss, args, dataset,
                    beam_size=None, limit=None):
    logger = logging.getLogger(args.pname)
    local_preds = []
    local_targets = []
    local_ids = []
    local_loss = []

    beam_size = beam_size if beam_size is not None else args.beam_size
    limit = limit if limit is not None else args.beam_size

    logger.debug("Starting inference")
    steps = [0]

    for _, data in enumerate(loader, 1):
        source_ids, source_mask, target_ids, data_ids = tuple(item for item in data)

        source_ids, source_mask, target_ids = source_ids.to(args.gpu), source_mask.to(args.gpu), target_ids.to(args.gpu)
        outputs = model_module(input_ids=source_ids, attention_mask=source_mask, labels=target_ids, output_attentions=False)
        lm_logits = outputs.logits
        lm_loss_fct = CrossEntropyLoss(ignore_index=model_module.config.pad_token_id, label_smoothing=args.label_smoothing)
        loss = lm_loss_fct(lm_logits.view(-1, lm_logits.size(-1)), target_ids.view(-1))
        local_loss.append(loss.item())
        target_ids = target_ids.to("cpu")

        max_gen_lengh = args.max_seq // 2
        if args.eval_full_beam:
            outputs = model_module.generate(
                input_ids=source_ids,
                attention_mask=source_mask,
                num_beams=beam_size,
                max_length=max_gen_lengh,
                use_cache=True,
                early_stopping=True,
                num_return_sequences=beam_size,
            )
            # For prediction certainty
            # outputs.scores[0].view(-1, beam_size, model_module.config.vocab_size).shape
            curr_batch_size = target_ids.shape[0]
            outputs = outputs.view(curr_batch_size, beam_size, -1).cpu().tolist()
            for i, beam_preds in enumerate(outputs):
                for pred in beam_preds[:limit]:
                    local_preds.append(pred)
                    local_targets.append(target_ids[i])
                    local_ids.append(data_ids[i])
        else:
            pred_ids = (
                model_module.generate(
                    input_ids=source_ids,
                    attention_mask=source_mask,
                    num_beams=beam_size,
                    max_length=max_gen_lengh,
                    use_cache=True,
                    early_stopping=True,
                )
                .cpu()
                .tolist()
            )
            local_preds.extend(pred_ids)
            local_targets.extend(target_ids)
            local_ids.extend(data_ids)

        progress = round(100 * len(set(local_ids)) / len(dataset))
        step = (progress // 20) * 20
        if step not in steps:
            steps.append(step)
            logger.debug(f"Inference progress {progress}%")
    
    if args.rank == 0:
        logger.debug(f"Inference finished")
        logger.debug(f"Gathering predictions")

    dist.gather_object(local_loss, global_loss if args.rank == 0 else None, dst=0)

    return local_preds, local_targets, local_ids, local_loss

def eval(model, split, args, save_dir):
    preds_per_round = math.ceil(args.beam_size / args.multi_predict_rounds)
    preds_per_round_per_gpu = math.ceil(preds_per_round / torch.cuda.device_count())
    subsequent_round_preds = math.ceil(preds_per_round / args.subsequent_round_inputs) + 1
    subsequent_round_preds_per_gpu = math.ceil(subsequent_round_preds / torch.cuda.device_count())


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

    global_loss = [None for _ in range(args.world_size)]

    local_preds, local_targets, local_ids, local_loss = get_predictions(loader, model_module, global_loss, args, dataset)

    all_loss = [item for sub in global_loss for item in sub]

    target_codes = tokenizer.batch_decode(local_targets, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    pred_codes = tokenizer.batch_decode(local_preds, skip_special_tokens=True, clean_up_tokenization_spaces=False)
    logger.debug(f"Decoding finished")


    pred_df = {
        "id": [],
        "pred": [],
        "target": [],
        "rank": [],
        "round": []
    }

    for curr_id in set(local_ids):
        indicies = [i for i in range(len(local_ids)) if local_ids[i] == curr_id][:preds_per_round]
        pred_df["id"].extend([local_ids[i] for i in indicies])
        pred_df["pred"].extend([pred_codes[i] for i in indicies])
        pred_df["target"].extend([target_codes[i] for i in indicies])
        pred_df["rank"].extend([i for i in range(1, preds_per_round + 1)])
        pred_df["round"].extend([1] * preds_per_round)

    for iteration in range(args.multi_predict_rounds - 1):
        new_inputs = {
            "id": [],
            "code": []
        }

        for curr_id in set(local_ids):
            new_input_indicies = [i for i in range(len(local_ids)) if local_ids[i] == curr_id][preds_per_round:preds_per_round + args.subsequent_round_inputs]
            new_inputs["id"].extend([local_ids[i] for i in new_input_indicies])
            new_inputs["code"].extend([pred_codes[i] for i in new_input_indicies])

        loader = create_loader(args.data_encoder_instance.load_and_update_split(split, new_inputs["id"], new_inputs["code"]), args, True)

        local_preds, local_targets, local_ids, local_loss = get_predictions(loader, model_module, global_loss, args, dataset, limit=subsequent_round_preds_per_gpu)

        all_loss = [item for sub in global_loss for item in sub]

        target_codes = tokenizer.batch_decode(local_targets, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        pred_codes = tokenizer.batch_decode(local_preds, skip_special_tokens=True, clean_up_tokenization_spaces=False)

        if args.rank == 0:
            for curr_id in set(local_ids):
                indicies = [i for i in range(len(local_ids)) if local_ids[i] == curr_id][:preds_per_round_per_gpu]
                pred_df["id"].extend([local_ids[i] for i in indicies])
                pred_df["pred"].extend([pred_codes[i] for i in indicies])
                pred_df["target"].extend([target_codes[i] for i in indicies])
                pred_df["rank"].extend([i for i in range(1, len(indicies) + 1)])
                pred_df["round"].extend([iteration + 2] * len(indicies))

    final_pred_df = {
        "id": [None for _ in range(args.world_size)],
        "pred": [None for _ in range(args.world_size)],
        "target": [None for _ in range(args.world_size)],
        "rank": [None for _ in range(args.world_size)],
        "round": [None for _ in range(args.world_size)]
    }
    dist.gather_object(pred_df["id"], final_pred_df["id"] if args.rank == 0 else None, dst=0)
    dist.gather_object(pred_df["pred"], final_pred_df["pred"] if args.rank == 0 else None, dst=0)
    dist.gather_object(pred_df["target"], final_pred_df["target"] if args.rank == 0 else None, dst=0)
    dist.gather_object(pred_df["rank"], final_pred_df["rank"] if args.rank == 0 else None, dst=0)
    dist.gather_object(pred_df["round"], final_pred_df["round"] if args.rank == 0 else None, dst=0)

    if args.rank == 0:
        final_pred_df["id"] = [item for sub in final_pred_df["id"] for item in sub]
        final_pred_df["pred"] = [item for sub in final_pred_df["pred"] for item in sub]
        final_pred_df["target"] = [item for sub in final_pred_df["target"] for item in sub]
        final_pred_df["rank"] = [item for sub in final_pred_df["rank"] for item in sub]
        final_pred_df["round"] = [item for sub in final_pred_df["round"] for item in sub]

        all_bleus, all_code_bleus = compute_single_bleus(final_pred_df['target'], final_pred_df['pred'])
        final_pred_df["bleu"] = all_bleus
        final_pred_df["code_bleu"] = all_code_bleus

        final_pred_df = pd.DataFrame(final_pred_df)

        bleu_score, code_bleu_score, em = compute_scores(final_pred_df["target"], final_pred_df["pred"], final_pred_df["id"])
        avg_loss = round(sum(all_loss) / len(all_loss), 3)
        logger.info(
            f"* BLEU: {bleu_score} ; CodeBLEU: {code_bleu_score} ; EM: {em} ; Loss: {avg_loss} ; Eval took: {datetime.now() - start}"
        )
        save_dir.mkdir(parents=True, exist_ok=True)
        final_pred_df.to_json(save_dir / f"{split}_predictions.json", orient="records", indent=2)

        scores = [bleu_score, code_bleu_score, em, avg_loss]
    else:
        scores = [None, None, None, None]

    dist.broadcast_object_list(scores, src=0)
    bleu_score, code_bleu_score, em, loss = scores[0], scores[1], scores[2], scores[3]
    return bleu_score, code_bleu_score, em, loss


def compute_single_bleus(targets, preds):
    bleus = []
    code_bleus = []
    for target, pred in zip(targets, preds):
        if len(target) == 0:
            score = 100.0 if len(pred) == 0 else 0.0
            bleus.append(score)
            code_bleus.append(score)
            continue
        if len(pred) == 0:
            bleus.append(0.0)
            code_bleus.append(0.0)
            continue
        if target == pred:
            bleus.append(100.0)
            code_bleus.append(100.0)
            continue
        bleu, code_bleu = compute_bleu_scores([target], [pred], sf=SmoothingFunction().method1)
        bleus.append(bleu)
        code_bleus.append(code_bleu)
    return bleus, code_bleus


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
    bleu_score, code_bleu_score = compute_bleu_scores(best_targets, best_preds)

    return bleu_score, code_bleu_score, em


def compute_bleu_scores(targets, preds, sf=None):
    if len(targets) != len(preds):
        raise Exception(f"Targets and preds size mismatch: {len(targets)} != {len(preds)}")
    format_score = lambda score: round(100 * score, 2)
    simple_tokenize = lambda text: text.strip().split()

    tokenized_references = [[simple_tokenize(target)] for target in targets]
    tokenized_hypotheses = [simple_tokenize(pred) for pred in preds]
    bleu_score = corpus_bleu(tokenized_references, tokenized_hypotheses, smoothing_function=sf)

    code_bleu_score = calc_code_bleu([targets], preds)

    return format_score(bleu_score), format_score(code_bleu_score)
