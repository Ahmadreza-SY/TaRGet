from transformers import (
    get_cosine_schedule_with_warmup,
)
from torch.optim import AdamW
import torch
from datetime import datetime, timedelta
from encoders import *
from utils import create_loader, save_stats
import pickle
from accelerate import Accelerator
from accelerate.utils import set_seed
from accelerate.logging import get_logger


def train(args):
    logger = get_logger("MAIN")
    args.accelerator = Accelerator()
    args.accelerator.state.deepspeed_plugin.deepspeed_config["gradient_accumulation_steps"] = args.gradient_accumulation
    logger.info(f"Arguments:\n {args}")
    set_seed(args.random_seed)
    logger.info(
        f"{args.accelerator.process_index}: Using device "
        + torch.cuda.get_device_name(args.accelerator.local_process_index),
        main_process_only=False,
    )

    args.train_dataset = pickle.load(open(str(args.output_dir / "splits" / f"train.pkl"), "rb"))
    args.valid_dataset = pickle.load(open(str(args.output_dir / "splits" / f"valid.pkl"), "rb"))
    args.tokenizer = args.model_tokenizer_class.from_pretrained(args.output_dir / "tokenizer")

    train_loader = create_loader(args.train_dataset, args)
    train_steps = int(args.epochs * len(train_loader))

    model = args.model_class.from_pretrained(args.model_path, trust_remote_code=True)
    # model.resize_token_embeddings(len(args.tokenizer))
    model.encoder.resize_token_embeddings(len(args.tokenizer))
    model.decoder.resize_token_embeddings(len(args.tokenizer))
    model.config.decoder_start_token_id = args.tokenizer.convert_tokens_to_ids(args.tokenizer.bos_token)
    model.config.pad_token_id = args.tokenizer.convert_tokens_to_ids(args.tokenizer.pad_token)
    model = model.to(args.accelerator.device)

    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=train_steps)

    model, optimizer, train_loader, scheduler = args.accelerator.prepare(model, optimizer, train_loader, scheduler)

    logger.info("***** Training *****")
    logger.info(f"Train data: {len(args.train_dataset)}")
    logger.info(f"Epochs: {args.epochs}")

    start = datetime.now()
    global_step = 0
    elapsed_time = timedelta()
    args.best_checkpoint = (1e16, 1)
    args.stats = {}
    args.stats["train_set_size"] = len(args.train_dataset)
    args.stats["valid_set_size"] = len(args.valid_dataset)
    args.stats["training_stats"] = {"epochs": []}
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = datetime.now()
        global_loss = []
        for _, data in enumerate(train_loader, 1):
            output = model(
                input_ids=data["input_ids"], labels=data["labels"], attention_mask=data["attention_mask"], return_dict=True
            )
            loss = output.loss
            loss_gathered = args.accelerator.gather_for_metrics(loss)
            global_loss.extend(loss_gathered.detach().float().tolist())
            args.accelerator.backward(loss)

            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

            global_step += 1

        # End of epoch
        train_time = datetime.now() - epoch_start
        elapsed_time += train_time
        epoch_stats = {}
        avg_loss = round(sum(global_loss) / len(global_loss), 3)
        epoch_stats["epoch"] = epoch
        epoch_stats["loss"] = avg_loss
        epoch_stats["train_duration"] = str(train_time)
        logger.info(
            "Step [{}/{}] ; Epoch [{}/{}] ; Train loss {} ; Elapsed time {} ; Train time per sample: {} s".format(
                global_step,
                train_steps,
                epoch,
                args.epochs,
                avg_loss,
                str(elapsed_time),
                round(train_time.total_seconds() / len(args.train_dataset), 3),
            )
        )

        valid_start = datetime.now()
        validate(args, model, epoch, epoch_stats)
        valid_time = datetime.now() - valid_start
        epoch_stats["valid_duration"] = str(valid_time)
        elapsed_time += valid_time

        args.stats["training_stats"]["epochs"].append(epoch_stats)
        if (epoch - args.best_checkpoint[1]) >= args.early_stop:
            logger.info(
                f"Early stopping since valid loss has not improved since best epoch {args.best_checkpoint[1]} for the last {args.early_stop} epochs"
            )
            args.stats["training_stats"]["last_epoch"] = epoch
            break

    training_time = datetime.now() - start
    args.stats["training_stats"]["training_time"] = str(training_time)
    if args.accelerator.is_main_process:
        save_stats(args)

    logger.info("Training completed in: " + str(training_time))


def validate(args, model, epoch, epoch_stats):
    logger = get_logger("MAIN")
    start = datetime.now()
    global_loss = []
    model.eval()
    validation_loader = create_loader(args.valid_dataset, args, True)
    validation_loader = args.accelerator.prepare(validation_loader)
    with torch.no_grad():
        for _, data in enumerate(validation_loader):
            output = model(
                input_ids=data["input_ids"], labels=data["labels"], attention_mask=data["attention_mask"], return_dict=True
            )
            loss = output.loss
            loss_gathered = args.accelerator.gather_for_metrics(loss)
            global_loss.extend(loss_gathered.detach().float().tolist())

    avg_loss = round(sum(global_loss) / len(global_loss), 3)
    logger.info(f"* Validation loss: {avg_loss} ; Eval took: {datetime.now() - start}")

    sel_score = avg_loss
    if sel_score < args.best_checkpoint[0]:
        args.best_checkpoint = (sel_score, epoch)
        logger.info(f"# Best checkpoint update: epoch {epoch} ; validation loss {avg_loss}")
        args.stats["training_stats"]["best_epoch"] = {"epoch": epoch, "valid_loss": avg_loss}

        save_dir = args.output_dir / f"checkpoint-best"
        save_dir.mkdir(parents=True, exist_ok=True)
        unwrapped_model = args.accelerator.unwrap_model(model)
        unwrapped_model.save_pretrained(
            save_dir,
            is_main_process=args.accelerator.is_main_process,
            save_function=args.accelerator.save,
        )

    epoch_stats["valid_loss"] = avg_loss
