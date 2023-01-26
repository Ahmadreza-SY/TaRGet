from pathlib import Path
from transformers import (
    PLBartForConditionalGeneration,
    PLBartTokenizer,
    get_linear_schedule_with_warmup,
)
from torch.utils.data import RandomSampler, DataLoader, SequentialSampler
from torch.utils.data.distributed import DistributedSampler
from DES import DistributedEvalSampler
from torch.optim import AdamW
import torch
from torch.nn import CrossEntropyLoss
import argparse
import torch.multiprocessing as mp
from torch.nn.parallel import DistributedDataParallel
from datetime import datetime, timedelta
import torch.distributed as dist
import logging
import os
from bleu import score, _bleu
from tuning_utils import write_lines
from encoders import *
import json
import sys
import maven_parser as mvnp
import git
import shutil

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%m-%d-%Y %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger("MAIN")

model_class = PLBartForConditionalGeneration


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--nodes", default=1, type=int, metavar="N", help="number of data loading workers")
    parser.add_argument("-g", "--gpus", default=1, type=int, help="number of gpus per node")
    parser.add_argument("-nr", "--node_rank", default=0, type=int)
    parser.add_argument(
        "-o", "--output_dir", required=True, type=str, help="output directory to save models and predictions"
    )
    parser.add_argument("-d", "--dataset_dir", required=True, type=str)
    parser.add_argument("-de", "--data_encoder", required=True, type=str)
    parser.add_argument(
        "-gt",
        "--ground_truth",
        default="repaired_body",
        type=str,
        choices=["repaired_body", "repair_changes_hsep", "repair_changes_stsep", "repair_changes_tok"],
    )
    parser.add_argument("-sc", "--scoring", default="em", type=str, choices=["bleu", "em", "sr"])
    parser.add_argument("-b", "--batch_size", required=True, type=int)
    parser.add_argument("-e", "--epochs", required=True, type=int)
    parser.add_argument("-m", "--max_seq", required=True, type=int)
    parser.add_argument("-ebs", "--eval_batch_size", default=16, type=int)
    parser.add_argument("-c", "--checkpoint_interval", default=3, type=int)
    parser.add_argument("-lr", "--learning_rate", default=5e-05, type=float)
    parser.add_argument("-ls", "--label_smoothing", default=0.1, type=float)
    parser.add_argument("-ts", "--train_size", default=0.8, type=float)
    parser.add_argument("-bs", "--beam_size", default=5, type=int)
    parser.add_argument("-s", "--random_seed", default=1234, type=int)
    parser.add_argument("-es", "--early_stop", default=10, type=int)
    parser.add_argument("-ss", "--sub_sample", dest="sub_sample", action="store_true")
    parser.set_defaults(sub_sample=False)
    parser.add_argument("-sr", "--sample_ratio", default=0.15, type=float)
    parser.add_argument("-to", "--test_only", dest="test_only", action="store_true")
    parser.set_defaults(test_only=False)
    parser.add_argument("-efb", "--eval_full_beam", dest="eval_full_beam", action="store_true")
    parser.set_defaults(eval_full_beam=False)
    # parser.add_argument("-boi", "--beam_out_index", default=0, type=int)

    args = parser.parse_args()
    args.output_dir = Path(args.output_dir)
    args.world_size = args.gpus * args.nodes
    args.model_name_or_path = "uclanlp/plbart-base"
    args.model_tokenizer_class = PLBartTokenizer
    try:
        args.data_encoder_class = getattr(sys.modules[__name__], args.data_encoder + "DataEncoder")
    except AttributeError:
        print(f"Invalid data encoder '{args.data_encoder}'")
        sys.exit()

    mp.spawn(run, nprocs=args.gpus, args=(args,))

    logger.info("All jobs done!")


def create_loader(dataset, args, eval_mode=False):
    if eval_mode:
        if args.world_size == 1:
            sampler = SequentialSampler(dataset)
        else:
            sampler = DistributedEvalSampler(dataset, num_replicas=args.world_size, rank=args.rank)
    else:
        if args.world_size == 1:
            sampler = RandomSampler(dataset)
        else:
            sampler = DistributedSampler(dataset, num_replicas=args.world_size, rank=args.rank)
    loader = DataLoader(dataset=dataset, batch_size=args.eval_batch_size if eval_mode else args.batch_size, sampler=sampler)
    return loader


def save_model(model, optimizer, scheduler, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    model_to_save = model.module if hasattr(model, "module") else model
    model_to_save.config.save_pretrained(output_dir)
    torch.save(model_to_save.state_dict(), output_dir / "pytorch_model.bin")
    torch.save(
        optimizer.state_dict(),
        output_dir / "optimizer.pt",
        _use_new_zipfile_serialization=False,
    )
    torch.save(
        scheduler.state_dict(),
        output_dir / "scheduler.pt",
        _use_new_zipfile_serialization=False,
    )


def run(gpu, args):
    rank = args.node_rank * args.gpus + gpu
    args.rank = rank
    args.gpu = gpu
    args.pname = f"{args.node_rank}-{args.rank}"
    logger = logging.getLogger(args.pname)
    if args.rank == 0:
        logger.info(f"Arguments:\n {args}")
        logger.info(f"Master node: {os.environ['MASTER_ADDR']}:{os.environ['MASTER_PORT']}")
    # Wait unitl all processes join
    logger.info(f"Joining process group ...")
    dist.init_process_group(backend="nccl", init_method="env://", world_size=args.world_size, rank=args.rank)
    logger.info(f"Joined!")
    torch.manual_seed(args.random_seed)
    if args.rank == 0:
        logger.info("All processes joined!")

    load_data(args)

    torch.cuda.set_device(gpu)

    if not args.test_only:
        train(gpu, args)

    test(gpu, args)


def load_data(args):
    data_encoder = args.data_encoder_class(args)
    args.train_dataset, args.valid_dataset, args.test_dataset = data_encoder.load_dataset()
    args.tokenizer = data_encoder.tokenizer

    if (args.output_dir / "stats.json").exists():
        with open(str(args.output_dir / "stats.json")) as f:
            args.stats = json.load(f)


def save_stats(args):
    if args.rank == 0:
        with open(str(args.output_dir / "stats.json"), "w") as f:
            f.write(json.dumps(args.stats, indent=2, sort_keys=False))


def train(gpu, args):
    train_loader = create_loader(args.train_dataset, args)
    train_steps = round(args.epochs * (len(args.train_dataset) / (args.batch_size * args.world_size)))
    # step_interval = 1 if train_steps < (args.epochs * 3) else train_steps // (args.epochs * 3)

    model = model_class.from_pretrained(args.model_name_or_path)
    model.resize_token_embeddings(len(args.tokenizer))
    model = model.to(gpu)
    logger.info(f"Using device " + torch.cuda.get_device_name(gpu))

    # define loss function (criterion) and optimizer
    no_decay = ["bias", "LayerNorm.weight"]
    optimizer_grouped_parameters = [
        {"params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)], "weight_decay": 0.0},
        {"params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)], "weight_decay": 0.0},
    ]
    warmup_steps = int(train_steps * 0.1)
    optimizer = AdamW(optimizer_grouped_parameters, lr=args.learning_rate, eps=1e-06, betas=(0.9, 0.98))
    scheduler = get_linear_schedule_with_warmup(optimizer, num_warmup_steps=warmup_steps, num_training_steps=train_steps)

    # Wrap the model
    model = DistributedDataParallel(model, device_ids=[gpu], output_device=gpu, find_unused_parameters=True)

    if args.rank == 0:
        logger.info("***** Training *****")
        logger.info(f"    Train data: {len(args.train_dataset)}")
        logger.info(f"    Epochs: {args.epochs}")

    start = datetime.now()
    global_step = 0
    elapsed_time = timedelta()
    args.best_checkpoint = (-1.0, 1)
    args.stats = {}
    args.stats["train_set_size"] = len(args.train_dataset)
    args.stats["valid_set_size"] = len(args.valid_dataset)
    args.stats["test_set_size"] = len(args.test_dataset)
    args.stats["training_stats"] = {"epochs": []}
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = datetime.now()
        model_module = model.module if hasattr(model, "module") else model
        epoch_loss, local_step = 0, 0
        for step, data in enumerate(train_loader, 1):
            optimizer.zero_grad(set_to_none=True)

            source_ids, source_mask, target_ids = tuple(item.to(gpu) for item in data[:-1])

            outputs = model_module(
                input_ids=source_ids, attention_mask=source_mask, labels=target_ids, output_attentions=False
            )

            lm_logits = outputs.logits
            lm_loss_fct = CrossEntropyLoss(
                ignore_index=model_module.config.pad_token_id, label_smoothing=args.label_smoothing
            )
            loss = lm_loss_fct(lm_logits.view(-1, lm_logits.size(-1)), target_ids.view(-1))

            loss.backward()
            optimizer.step()
            scheduler.step()
            global_step += 1
            local_step += 1
            batch_loss = loss.item()
            epoch_loss += batch_loss

        # End of epoch
        train_time = datetime.now() - epoch_start
        elapsed_time += train_time
        epoch_stats = {}
        if args.rank == 0:
            avg_loss = round(epoch_loss / local_step, 3)
            epoch_stats["epoch"] = epoch
            epoch_stats["loss"] = avg_loss
            epoch_stats["train_duration"] = str(train_time)
            logger.info(
                "    Step [{}/{}], Epoch [{}/{}], Train loss {}, Elapsed time {}".format(
                    global_step,
                    train_steps,
                    epoch,
                    args.epochs,
                    avg_loss,
                    str(elapsed_time),
                )
            )

        valid_start = datetime.now()
        valid_output_dir = args.output_dir / f"checkpoint-last"
        # if args.rank == 0:
        #     save_model(model, optimizer, scheduler, valid_output_dir)

        bleu_score, em, sr = eval(model, args.valid_dataset, args, valid_output_dir, args.output_dir)
        if args.scoring == "em":
            sel_score = em
        elif args.scoring == "bleu":
            sel_score = bleu_score
        elif args.scoring == "sr":
            sel_score = sr
        if sel_score > args.best_checkpoint[0]:
            args.best_checkpoint = (sel_score, epoch)
            if args.rank == 0:
                logger.info(f"Best checkpoint update: epoch {epoch} ; BLEU {bleu_score} ; EM {em} ; SR {sr}")
                args.stats["training_stats"]["best_epoch"] = {"epoch": epoch, "bleu": bleu_score, "em": em, "sr": sr}
                save_model(model, optimizer, scheduler, args.output_dir / f"checkpoint-best")

        valid_time = datetime.now() - valid_start
        epoch_stats["bleu"] = bleu_score
        epoch_stats["em"] = em
        epoch_stats["sr"] = sr
        epoch_stats["valid_duration"] = str(valid_time)
        args.stats["training_stats"]["epochs"].append(epoch_stats)
        elapsed_time += valid_time

        if (epoch - args.best_checkpoint[1]) >= args.early_stop:
            if args.rank == 0:
                logger.info(
                    f"Early stopping since valid {args.scoring} has not improved since best epoch {args.best_checkpoint[1]} for the last {args.early_stop} epochs"
                )
                args.stats["training_stats"]["last_epoch"] = epoch
            break

    if args.rank == 0:
        training_time = datetime.now() - start
        logger.info("Training completed in: " + str(training_time))
        args.stats["training_stats"]["training_time"] = str(training_time)

    save_stats(args)


def test(gpu, args):
    if args.rank == 0:
        logger.info(f"Loading best checkpoint")
    best_checkpoint_path = args.output_dir / f"checkpoint-best"
    model = model_class.from_pretrained(best_checkpoint_path)
    model.resize_token_embeddings(len(args.tokenizer))
    model = model.to(gpu)
    model = DistributedDataParallel(model, device_ids=[gpu], output_device=gpu, find_unused_parameters=True)

    if args.rank == 0:
        logger.info(f"Testing with best checkpoint on validation set")
    bleu_score, em, sr = eval(model, args.valid_dataset, args, best_checkpoint_path, args.output_dir)

    if args.rank == 0:
        logger.info(f"Testing with best checkpoint on test set")
    bleu_score, em, sr = eval(model, args.test_dataset, args, args.output_dir, args.output_dir)
    args.stats["test_results"] = {"bleu": bleu_score, "em": em, "sr": sr}

    save_stats(args)


def compute_single_bleus(targets, preds, output_dir):
    bleus = []
    target_file = output_dir / "temp_target.txt"
    pred_file = output_dir / "temp_pred.txt"
    for target, pred in zip(targets, preds):
        if len(target) == 0:
            bleus.append(100.0 if len(pred) == 0 else 0.0)
            continue
        if len(pred) == 0:
            bleus.append(0.0)
            continue
        write_lines(str(target_file), [target])
        write_lines(str(pred_file), [pred])
        bleu = _bleu(str(target_file), str(pred_file))
        bleus.append(bleu)

    target_file.unlink()
    pred_file.unlink()
    return bleus


def plaus_score(predictions, base_output_dir):
    with open(f"{base_output_dir}/splits/test.json", 'r') as f:
        test_objs = json.load(f)[:len(predictions)]

    test_pairs = [(predictions[i], test_objs[i]) for i in range(len(predictions))]
    test_pairs.sort(key=lambda a: a[1]['aCommit'])

    git_dir = base_output_dir / "git"
    if not git_dir.exists() or not git_dir.stat().st_size > 0:
        os.mkdir(git_dir)

    successes = 0
    verdicts = []
    curr_commit = None
    curr_repo = None

    for p, t in test_pairs:
        repo_path = t["ID"].split(':')[0]
        clone_dir = git_dir / repo_path
        if not clone_dir.exists() or not clone_dir.stat().st_size > 0:
            git_repo = git.Repo.clone_from(f"https://github.com/{repo_path}.git", clone_dir)
        else:
            git_repo = git.Repo(clone_dir)

        commit = t['aCommit']
        if commit != curr_commit or repo_path != curr_repo:
            git_repo.git.checkout(commit)
            curr_repo = repo_path
            curr_commit = commit

        test_file = clone_dir / t['aPath']

        with open(test_file, 'r') as orig_file:
            contents = orig_file.read()

        if len(t['hunk']['targetChanges']) > 0:
            contents = contents.split('\n')
            target_line = t['hunk']['targetChanges'][0]['lineNo'] - 1
            for tc in t['hunk']['targetChanges'][::-1]:
                del contents[tc['lineNo'] - 1]
            contents.insert(target_line, p)
            contents = '\n'.join(contents)

        else:
            test_method = t['bSource']['code'].split('\n')
            start_line = t['bSource']['startLine']
            target_line = t['hunk']['sourceChanges'][0]['lineNo'] - start_line
            for tc in t['hunk']['sourceChanges'][::-1]:
                del test_method[tc['lineNo'] - start_line]
            test_method.insert(target_line, p)
            contents.replace(t['aSource']['code'], '\n'.join(test_method))

        with open(test_file, 'w') as orig_file:
            orig_file.write(contents)

        test_simple_name = t["name"].split(".")[-1].replace("()", "")
        log_path = (
                base_output_dir
                / "testLogs"
                / t['aCommit']
                / test_simple_name
        )
        verdict = mvnp.compile_and_run_test(clone_dir, test_file, test_simple_name, log_path)

        verdicts.append(verdict.status)

        if verdict.status == verdict.SUCCESS:
            successes += 1

        git_repo.git.reset('--hard')

    shutil.rmtree(base_output_dir / "testLogs")

    return successes / len(test_objs), verdicts


def eval(model, dataset, args, output_dir, base_output_dir):
    logger = logging.getLogger(args.pname)
    if args.rank == 0:
        logger.info(f"Eval data: {len(dataset)}")

    start = datetime.now()

    tokenizer = args.tokenizer
    model.eval()
    model_module = model.module if hasattr(model, "module") else model
    loader = create_loader(dataset, args, True)

    global_preds = [None for _ in range(args.world_size)]
    global_targets = [None for _ in range(args.world_size)]
    global_ids = [None for _ in range(args.world_size)]

    local_preds = []
    local_targets = []
    local_ids = []
    for step, data in enumerate(loader, 1):
        source_ids, source_mask, target_ids, data_ids = tuple(item for item in data)
        source_ids, source_mask = source_ids.to(args.gpu), source_mask.to(args.gpu)
        if args.eval_full_beam:
            outputs = model_module.generate(
                input_ids=source_ids,
                attention_mask=source_mask,
                num_beams=args.beam_size,
                max_length=args.max_seq,
                use_cache=True,
                early_stopping=True,
                num_return_sequences=args.beam_size,
                output_scores=True,
                return_dict_in_generate=True,
            )
            # For prediction certainty
            # outputs.scores[0].view(-1, args.beam_size, model_module.config.vocab_size).shape
            curr_batch_size = target_ids.shape[0]
            batch_preds = outputs.sequences.view(curr_batch_size, args.beam_size, -1).cpu()
            pred_ids = torch.zeros((curr_batch_size, batch_preds.shape[2]))
            for i, preds in enumerate(batch_preds):
                em_ind = -1
                for j, seq in enumerate(preds):
                    seq_code = tokenizer.decode(seq, skip_special_tokens=True, clean_up_tokenization_spaces=False)
                    target_code = tokenizer.decode(
                        target_ids[i], skip_special_tokens=True, clean_up_tokenization_spaces=False
                    )
                    if seq_code == target_code:
                        em_ind = j
                        break
                if em_ind == -1:
                    pred_ids[i] = preds[0]
                else:
                    pred_ids[i] = preds[em_ind]
        else:
            pred_ids = model_module.generate(
                input_ids=source_ids,
                attention_mask=source_mask,
                num_beams=args.beam_size,
                max_length=args.max_seq,
                use_cache=True,
                early_stopping=True,
            )

        local_preds.extend(list(pred_ids.cpu()))
        local_targets.extend(target_ids)
        local_ids.extend(data_ids)

    dist.gather_object(local_preds, global_preds if args.rank == 0 else None, dst=0)
    dist.gather_object(local_targets, global_targets if args.rank == 0 else None, dst=0)
    dist.gather_object(local_ids, global_ids if args.rank == 0 else None, dst=0)
    if args.rank == 0:
        output_dir = output_dir / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        all_targets = [target for sub in global_targets for target in sub]
        all_preds = [pred for sub in global_preds for pred in sub]
        all_ids = [pred for sub in global_ids for pred in sub]
        logger.debug(f"    Gathered {len(all_preds)} , {len(all_targets)} targets and predictions")
        target_codes = tokenizer.batch_decode(all_targets, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        pred_codes = tokenizer.batch_decode(all_preds, skip_special_tokens=True, clean_up_tokenization_spaces=False)
        all_bleus = compute_single_bleus(target_codes, pred_codes, output_dir)

        target_file = output_dir / f"fixed_targets.txt"
        write_lines(target_file, target_codes)
        pred_file = output_dir / f"fixed_preds.txt"
        write_lines(pred_file, pred_codes)
        ids_file = output_dir / f"ids.txt"
        write_lines(ids_file, all_ids)
        bleus_file = output_dir / f"bleus.txt"
        write_lines(bleus_file, [str(bleu) for bleu in all_bleus])

        bleu_score, em = score(str(target_file), str(pred_file))

        success_rate, verdicts = plaus_score(str(target_file), base_output_dir)
        verdicts_file = output_dir / f"verdicts.txt"
        write_lines(verdicts_file, verdicts)

        logger.info(f"*** BLEU: {bleu_score} ; EM: {em} ; SR: {success_rate} *** "
                    f"Eval completed in: {datetime.now() - start}")

        scores = [bleu_score, em, success_rate]
    else:
        scores = [None, None, None]

    dist.broadcast_object_list(scores, src=0)
    bleu_score, em, sr = scores[0], scores[1], scores[2]
    return bleu_score, em, sr


if __name__ == "__main__":
    main()
