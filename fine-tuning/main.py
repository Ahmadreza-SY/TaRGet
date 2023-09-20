import sys

sys.path.append("../common")
from pathlib import Path
from transformers import (
    PLBartForConditionalGeneration,
    PLBartTokenizer,
    RobertaTokenizerFast,
    T5ForConditionalGeneration,
    AutoTokenizer,
    CodeGenForCausalLM,
)
import torch
import argparse
import torch.multiprocessing as mp
import torch.distributed as dist
import logging
import os
from encoders import *
import json
from train import train
from eval import test
from dataset import EncDecDataset, CodeGenDataset

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--nodes", default=1, type=int, metavar="N", help="number of data loading workers")
    parser.add_argument("-g", "--gpus", default=1, type=int, help="number of gpus per node")
    parser.add_argument("-nr", "--node_rank", default=0, type=int)
    parser.add_argument(
        "-o", "--output_dir", required=True, type=str, help="output directory to save models and predictions"
    )
    parser.add_argument("-d", "--dataset_dir", type=str)
    parser.add_argument("-de", "--data_encoder", type=str)
    parser.add_argument("-sc", "--scoring", default="em", type=str, choices=["bleu", "em"])
    parser.add_argument("-b", "--batch_size", type=int)
    parser.add_argument("-e", "--epochs", type=int)
    parser.add_argument("-ml", "--max_length", required=True, type=int)
    parser.add_argument("-c", "--checkpoint_interval", default=2, type=int)
    parser.add_argument("-lr", "--learning_rate", default=1e-5, type=float)
    parser.add_argument("-ls", "--label_smoothing", default=0.1, type=float)
    parser.add_argument("-ts", "--train_size", default=0.8, type=float)
    parser.add_argument("-bs", "--beam_size", default=5, type=int)
    parser.add_argument("-s", "--random_seed", default=1234, type=int)
    parser.add_argument("-es", "--early_stop", default=10, type=int)
    parser.add_argument("-ev", "--eval", dest="eval", action="store_true")
    parser.set_defaults(eval=False)
    parser.add_argument("-tr", "--train", dest="train", action="store_true")
    parser.set_defaults(train=False)
    parser.add_argument("-m", "--model", default="plbart", type=str, choices=["plbart", "codet5", "codegen"])

    logger = logging.getLogger("MAIN")

    args = parser.parse_args()
    args.output_dir = Path(args.output_dir)
    args.world_size = args.gpus * args.nodes

    os.environ["TOKENIZERS_PARALLELISM"] = "true"
    if args.model == "codet5":
        args.model_name_or_path = "salesforce/codet5-base"
        args.model_class = T5ForConditionalGeneration
        args.model_tokenizer_class = RobertaTokenizerFast
        args.dataset_class = EncDecDataset
    elif args.model == "plbart":
        args.model_name_or_path = "uclanlp/plbart-base"
        args.model_class = PLBartForConditionalGeneration
        args.model_tokenizer_class = PLBartTokenizer
        args.dataset_class = EncDecDataset
    elif args.model == "codegen":
        args.model_name_or_path = "salesforce/codegen-350M-mono"
        args.model_class = CodeGenForCausalLM
        args.model_tokenizer_class = AutoTokenizer
        args.dataset_class = CodeGenDataset

    if args.train:
        try:
            args.data_encoder_class = getattr(sys.modules[__name__], args.data_encoder + "DataEncoder")
        except AttributeError:
            print(f"Invalid data encoder '{args.data_encoder}'")
            sys.exit()
        load_data(args)
        logger.info(f"Master node: {os.environ['MASTER_ADDR']}:{os.environ['MASTER_PORT']}")
        mp.spawn(run, nprocs=args.gpus, args=(args,))
        logger.info("All jobs done!")
    elif args.eval:
        test(args)


def run(gpu, args):
    rank = args.node_rank * args.gpus + gpu
    args.rank = rank
    args.gpu = gpu
    args.pname = f"{args.node_rank}-{args.rank}"
    logger = logging.getLogger(args.pname)
    # Wait unitl all processes join
    logger.info(f"Joining process group ...")
    dist.init_process_group(backend="nccl", init_method="env://", world_size=args.world_size, rank=args.rank)
    logger.info(f"Joined!")
    torch.manual_seed(args.random_seed)
    if args.rank == 0:
        logger.info("All processes joined!")

    torch.cuda.set_device(gpu)
    train(gpu, args)


def load_data(args):
    logger = logging.getLogger("MAIN")
    data_encoder = args.data_encoder_class(args)
    dataset_splits = list(data_encoder.load_dataset())
    args.tokenizer = data_encoder.tokenizer
    logger.info(f"Arguments:\n {args}")
    args.train_dataset, args.valid_dataset, args.test_dataset = dataset_splits
    if (args.output_dir / "stats.json").exists():
        with open(str(args.output_dir / "stats.json")) as f:
            args.stats = json.load(f)


if __name__ == "__main__":
    main()
