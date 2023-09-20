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
import argparse
import torch.multiprocessing as mp
import logging
import os
from encoders import *
from train import run
from eval import test
from dataset import EncDecDataset, CodeGenDataset

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s |   %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)


def main():
    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers()
    encode_parser = sub_parsers.add_parser("encode")
    finetune_parser = sub_parsers.add_parser("finetune")
    test_parser = sub_parsers.add_parser("test")

    encode_parser.set_defaults(func=encode)
    add_common_arguments(encode_parser)
    encode_parser.add_argument("-d", "--dataset_dir", required=True, type=str)
    encode_parser.add_argument("-de", "--data_encoder", required=True, type=str)
    encode_parser.add_argument("-ts", "--train_size", default=0.8, type=float)

    finetune_parser.set_defaults(func=finetune)
    add_common_arguments(finetune_parser)
    finetune_parser.add_argument("-n", "--nodes", default=1, type=int, metavar="N", help="number of data loading workers")
    finetune_parser.add_argument("-g", "--gpus", default=1, type=int, help="number of gpus per node")
    finetune_parser.add_argument("-nr", "--node_rank", default=0, type=int)
    finetune_parser.add_argument("-b", "--batch_size", required=True, type=int)
    finetune_parser.add_argument("-e", "--epochs", required=True, type=int)
    finetune_parser.add_argument("-lr", "--learning_rate", required=True, type=float)
    finetune_parser.add_argument("-es", "--early_stop", default=10, type=int)

    test_parser.set_defaults(func=test)
    add_common_arguments(test_parser)
    test_parser.add_argument("-bs", "--beam_size", default=5, type=int)

    logger = logging.getLogger("MAIN")

    args = parser.parse_args()
    args.random_seed = 1234
    args.output_dir = Path(args.output_dir)
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

    logger.info(f"Arguments:\n {args}")
    args.func(args)


def add_common_arguments(sub_parser):
    sub_parser.add_argument("-m", "--model", required=True, type=str, choices=["plbart", "codet5", "codegen"])
    sub_parser.add_argument(
        "-o", "--output_dir", required=True, type=str, help="output directory to save models and predictions"
    )
    sub_parser.add_argument("-ml", "--max_length", required=True, type=int)


def encode(args):
    try:
        data_encoder_class = getattr(sys.modules[__name__], args.data_encoder + "DataEncoder")
    except AttributeError:
        print(f"Invalid data encoder '{args.data_encoder}'")
        sys.exit()
    data_encoder = data_encoder_class(args)
    data_encoder.create_datasets()


def finetune(args):
    logger = logging.getLogger("MAIN")
    args.world_size = args.gpus * args.nodes
    logger.info(f"Master node: {os.environ['MASTER_ADDR']}:{os.environ['MASTER_PORT']}")
    mp.spawn(run, nprocs=args.gpus, args=(args,))
    logger.info("All jobs done!")


if __name__ == "__main__":
    main()
