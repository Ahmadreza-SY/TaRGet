from transformers import (
    get_linear_schedule_with_warmup,
)
from torch.optim import AdamW
import torch.distributed as dist
import torch
from torch.nn import CrossEntropyLoss
from torch.nn.parallel import DistributedDataParallel
from datetime import datetime, timedelta
from encoders import *
from utils import create_loader, save_stats
from eval import eval


def train(gpu, args):
    logger = logging.getLogger(args.pname)
    args.logger = logger
    train_loader = create_loader(args.train_dataset, args)
    train_steps = round(args.epochs * (len(args.train_dataset) / (args.batch_size * args.world_size)))
    # step_interval = 1 if train_steps < (args.epochs * 3) else train_steps // (args.epochs * 3)

    model = args.model_class.from_pretrained(args.model_name_or_path)
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
        logger.info(f"Train data: {len(args.train_dataset)}")
        logger.info(f"Epochs: {args.epochs}")

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

        global_loss = [None for _ in range(args.world_size)]
        local_loss = []
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
            local_loss.append(loss.item())

        # End of epoch
        train_time = datetime.now() - epoch_start
        elapsed_time += train_time
        epoch_stats = {}
        dist.gather_object(local_loss, global_loss if args.rank == 0 else None, dst=0)
        if args.rank == 0:
            all_loss = [item for sub in global_loss for item in sub]
            avg_loss = round(sum(all_loss) / len(all_loss), 3)
            epoch_stats["epoch"] = epoch
            epoch_stats["loss"] = avg_loss
            epoch_stats["train_duration"] = str(train_time)
            logger.info(
                "Step [{}/{}] ; Epoch [{}/{}] ; Train loss {} ; Elapsed time {}".format(
                    global_step,
                    train_steps,
                    epoch,
                    args.epochs,
                    avg_loss,
                    str(elapsed_time),
                )
            )

        if epoch % args.checkpoint_interval == 0:
            valid_start = datetime.now()
            validate(args, model, epoch, epoch_stats)
            valid_time = datetime.now() - valid_start
            epoch_stats["valid_duration"] = str(valid_time)
            elapsed_time += valid_time

        args.stats["training_stats"]["epochs"].append(epoch_stats)
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


def validate(args, model, epoch, epoch_stats):
    bleu_score, code_bleu_score, em, loss = eval(model, "valid", args, args.output_dir / f"checkpoint-last")
    if args.scoring == "em":
        sel_score = em
    elif args.scoring == "bleu":
        sel_score = bleu_score
    elif args.scoring == "code_bleu":
        sel_score = code_bleu_score
    if sel_score > args.best_checkpoint[0]:
        args.best_checkpoint = (sel_score, epoch)
        if args.rank == 0:
            args.logger.info(
                f"# Best checkpoint update: epoch {epoch} ; BLEU {bleu_score} ; CodeBLEU: {code_bleu_score} ; EM {em}"
            )
            args.stats["training_stats"]["best_epoch"] = {
                "epoch": epoch,
                "bleu": bleu_score,
                "code_bleu": code_bleu_score,
                "em": em,
            }
            save_model(model, args.output_dir / f"checkpoint-best")

    epoch_stats["bleu"] = bleu_score
    epoch_stats["code_bleu"] = code_bleu_score
    epoch_stats["em"] = em
    epoch_stats["valid_loss"] = loss


def save_model(model, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    model_to_save = model.module if hasattr(model, "module") else model
    model_to_save.save_pretrained(output_dir)
