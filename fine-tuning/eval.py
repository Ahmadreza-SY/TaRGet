from encoders import *
import pandas as pd
from datetime import datetime
from utils import save_stats, get_data_encoder_class
from nltk.translate.bleu_score import corpus_bleu
from CodeBLEU.code_bleu import calc_code_bleu
from tqdm import tqdm
import pickle
import json
from accelerate import Accelerator
from accelerate.utils import set_seed
from accelerate.logging import get_logger


def test(args):
    logger = get_logger("MAIN", log_level=args.log_level)
    args.accelerator = Accelerator()
    logger.info(f"Arguments:\n {args}")
    set_seed(args.random_seed)

    logger.info("***** Testing *****")
    if (args.output_dir / "stats.json").exists():
        with open(str(args.output_dir / "stats.json")) as f:
            args.stats = json.load(f)
    else:
        logger.info("No stats.json found, creating a new one.")
        args.stats = {}

    args.valid_ds = pd.read_json(args.output_dir / "splits" / f"valid.json")
    args.test_ds = pd.read_json(args.output_dir / "splits" / f"test.json")
    if args.mask_projects is not None:
        args.valid_ds = args.valid_ds[args.valid_ds["project"].isin(args.mask_projects)].reset_index(drop=True)
        args.test_ds = args.test_ds[args.test_ds["project"].isin(args.mask_projects)].reset_index(drop=True)
    args.stats["test_set_size"] = len(args.test_ds)

    args.tokenizer = args.model_tokenizer_class.from_pretrained(args.output_dir / "tokenizer")

    best_checkpoint_path = args.output_dir / f"checkpoint-best"
    model = args.model_class.from_pretrained(best_checkpoint_path, trust_remote_code=True)
    model = args.accelerator.prepare(model)

    logger.info(f"Testing with best checkpoint on Valid set with size {len(args.valid_ds)}")
    bleu_score, code_bleu_score, em = eval(model, "valid", args, best_checkpoint_path)
    args.stats["valid_results"] = {"bleu": bleu_score, "code_bleu": code_bleu_score, "em": em}

    logger.info(f"Testing with best checkpoint on Test set set with size {len(args.test_ds)}")
    bleu_score, code_bleu_score, em = eval(model, "test", args, args.output_dir)
    args.stats["test_results"] = {"bleu": bleu_score, "code_bleu": code_bleu_score, "em": em}

    save_stats(args)


def eval(model, split, args, save_dir):
    logger = get_logger("MAIN", log_level=args.log_level)
    if split == "valid":
        dataset = args.valid_ds
    elif split == "test":
        dataset = args.test_ds

    start = datetime.now()

    data_encoder_class = get_data_encoder_class(args.data_encoder)
    tokenizer = args.tokenizer
    dataset_obj = pickle.load(open(str(args.output_dir / "splits" / f"valid.pkl"), "rb"))
    pad_id, eos_id = dataset_obj.get_pad_eos_for_generation(tokenizer)
    decoder_sid = dataset_obj.get_decoder_start_token_id(tokenizer)
    model.eval()

    predictions = []
    for _, row in tqdm(dataset.iterrows(), total=len(dataset), desc="Generating"):
        input_ids = dataset_obj.get_inference_input(row, tokenizer).to(args.accelerator.device)
        outputs = model.generate(
            input_ids,
            max_length=args.max_length,
            num_beams=args.beam_size,
            num_return_sequences=args.beam_size,
            early_stopping=True,
            use_cache=True,
            pad_token_id=pad_id,
            eos_token_id=eos_id,
            decoder_start_token_id=decoder_sid,
        )
        outputs = dataset_obj.get_new_generated_tokens(outputs, input_ids)
        preds = data_encoder_class.decode_outputs(row, outputs, tokenizer)
        predictions.append(preds)

    pred_df = pd.DataFrame(predictions)
    bleu_score, code_bleu_score, em = compute_scores(pred_df)
    logger.info(f"* BLEU: {bleu_score} ; CodeBLEU: {code_bleu_score} ; EM: {em} ; Eval took: {datetime.now() - start}")
    save_dir.mkdir(parents=True, exist_ok=True)
    pred_df.to_json(save_dir / f"{split}_predictions.json", orient="records", indent=2)
    return bleu_score, code_bleu_score, em


def compute_scores(pred_df):
    eval_size = pred_df["ID"].nunique()
    em_size = 0
    best_preds = []
    targets = []
    for _, row in pred_df.iterrows():
        beam_outputs = row["preds"]
        target = row["target"]
        best_pred = beam_outputs[0]
        for output in beam_outputs:
            if output == target:
                em_size += 1
                best_pred = output
                break
        best_preds.append(best_pred)
        targets.append(target)

    em = round(em_size / eval_size * 100, 2)
    bleu_score, code_bleu_score = compute_bleu_scores(targets, best_preds)
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
