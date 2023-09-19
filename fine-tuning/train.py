from transformers import (
    get_cosine_schedule_with_warmup,
)
from torch.optim import AdamW
import torch.distributed as dist
import torch
from torch.nn.parallel import DistributedDataParallel
from datetime import datetime, timedelta
from encoders import *
from utils import create_loader, save_stats
from transformers import Adafactor


def train(gpu, args):
    logger = logging.getLogger(args.pname)
    args.logger = logger
    train_loader = create_loader(args.train_dataset, args)
    train_steps = int(args.epochs * len(train_loader))

    model = args.model_class.from_pretrained(args.model_name_or_path)
    model.resize_token_embeddings(len(args.tokenizer))
    model = model.to(gpu)
    logger.info(f"Using device " + torch.cuda.get_device_name(gpu))

    # optimizer = Adafactor(model.parameters(), lr=args.learning_rate, scale_parameter=False, relative_step=False)
    optimizer = AdamW(model.parameters(), lr=args.learning_rate)
    scheduler = get_cosine_schedule_with_warmup(optimizer, num_warmup_steps=0, num_training_steps=train_steps)

    model = DistributedDataParallel(model, device_ids=[gpu], output_device=gpu)

    if args.rank == 0:
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
    args.stats["test_set_size"] = len(args.test_dataset)
    args.stats["training_stats"] = {"epochs": []}
    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = datetime.now()
        # model_module = model.module if hasattr(model, "module") else model

        global_loss = [None for _ in range(args.world_size)]
        local_loss = []
        for _, data in enumerate(train_loader, 1):
            optimizer.zero_grad(set_to_none=True)

            data = {
                "input_ids": data["input_ids"].to(gpu),
                "labels": data["labels"].to(gpu),
                "attention_mask": data["attention_mask"].to(gpu),
            }
            output = model(
                input_ids=data["input_ids"], labels=data["labels"], attention_mask=data["attention_mask"], return_dict=True
            )
            loss = output.loss

            loss.backward()
            optimizer.step()
            scheduler.step()
            local_loss.append(loss.item())
            global_step += 1

        # End of epoch
        train_time = datetime.now() - epoch_start
        elapsed_time += train_time
        epoch_stats = {}
        dist.gather_object(local_loss, global_loss if args.rank == 0 else None, dst=0)
        if args.rank == 0:
            train_loss = [item for sub in global_loss for item in sub]
            avg_loss = round(sum(train_loss) / len(train_loss), 3)
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
                    f"Early stopping since valid loss has not improved since best epoch {args.best_checkpoint[1]} for the last {args.early_stop} epochs"
                )
                args.stats["training_stats"]["last_epoch"] = epoch
            break

    if args.rank == 0:
        training_time = datetime.now() - start
        logger.info("Training completed in: " + str(training_time))
        args.stats["training_stats"]["training_time"] = str(training_time)

    save_stats(args)


def validate(args, model, epoch, epoch_stats):
    start = datetime.now()
    global_loss = [None for _ in range(args.world_size)]
    local_loss = []
    model.eval()
    validation_loader = create_loader(args.valid_dataset, args, True)
    with torch.no_grad():
        for _, data in enumerate(validation_loader):
            data = {
                "input_ids": data["input_ids"].to(args.gpu),
                "labels": data["labels"].to(args.gpu),
                "attention_mask": data["attention_mask"].to(args.gpu),
            }
            output = model(
                input_ids=data["input_ids"], labels=data["labels"], attention_mask=data["attention_mask"], return_dict=True
            )
            loss = output.loss
            local_loss.append(loss.item())

    dist.gather_object(local_loss, global_loss if args.rank == 0 else None, dst=0)
    dist.broadcast_object_list(global_loss, src=0)
    valid_loss = [item for sub in global_loss for item in sub]
    avg_loss = round(sum(valid_loss) / len(valid_loss), 3)
    if args.rank == 0:
        args.logger.info(f"* Validation loss: {avg_loss} ; Eval took: {datetime.now() - start}")
    model.train()

    sel_score = avg_loss
    if sel_score < args.best_checkpoint[0]:
        args.best_checkpoint = (sel_score, epoch)
        if args.rank == 0:
            args.logger.info(f"# Best checkpoint update: epoch {epoch} ; validation loss {avg_loss}")
            args.stats["training_stats"]["best_epoch"] = {"epoch": epoch, "valid_loss": avg_loss}
            save_model(model, args.tokenizer, args.output_dir / f"checkpoint-best")

    epoch_stats["valid_loss"] = avg_loss


def save_model(model, tokenizer, output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    model_to_save = model.module if hasattr(model, "module") else model
    model_to_save.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
