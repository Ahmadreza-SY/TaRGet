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
    AutoModelForSeq2SeqLM,
)
import argparse
import logging
import os
from train import train
from eval import test
from dataset import EncDecDataset, PLBARTDataset, CodeGenDataset
from utils import get_data_encoder_class

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
    encode_parser.add_argument("-tf", "--train_fraction", default=1.0, type=float)

    finetune_parser.set_defaults(func=train)
    add_common_arguments(finetune_parser)
    finetune_parser.add_argument("-n", "--num_nodes", default=1, type=int)
    finetune_parser.add_argument("-b", "--batch_size", required=True, type=int)
    finetune_parser.add_argument("-e", "--epochs", required=True, type=int)
    finetune_parser.add_argument("-lr", "--learning_rate", required=True, type=float)
    finetune_parser.add_argument("-es", "--early_stop", default=10, type=int)
    finetune_parser.add_argument("-ga", "--gradient_accumulation", default=1, type=int)

    test_parser.set_defaults(func=test)
    add_common_arguments(test_parser)
    test_parser.add_argument("-de", "--data_encoder", required=True, type=str)
    test_parser.add_argument("-bs", "--beam_size", default=5, type=int)

    args = parser.parse_args()
    args.random_seed = 1234
    args.output_dir = Path(args.output_dir)
    os.environ["TOKENIZERS_PARALLELISM"] = "true"
    if args.model == "codet5":
        args.model_class = T5ForConditionalGeneration
        args.model_tokenizer_class = RobertaTokenizerFast
        args.dataset_class = EncDecDataset
    elif args.model == "plbart":
        args.model_class = PLBartForConditionalGeneration
        args.model_tokenizer_class = PLBartTokenizer
        args.dataset_class = PLBARTDataset
    elif args.model == "codegen":
        args.model_class = CodeGenForCausalLM
        args.model_tokenizer_class = AutoTokenizer
        args.dataset_class = CodeGenDataset
    elif args.model == "codet5p":
        args.model_class = AutoModelForSeq2SeqLM
        args.model_tokenizer_class = AutoTokenizer
        args.dataset_class = EncDecDataset

    args.func(args)


def add_common_arguments(sub_parser):
    sub_parser.add_argument("-m", "--model", required=True, type=str, choices=["plbart", "codet5", "codegen", "codet5p"])
    sub_parser.add_argument("-mp", "--model_path", type=str)
    sub_parser.add_argument(
        "-o", "--output_dir", required=True, type=str, help="output directory to save models and predictions"
    )
    sub_parser.add_argument("-ml", "--max_length", required=True, type=int)
    sub_parser.add_argument("-ll", "--log_level", default="INFO", type=str)


def encode(args):
    logger = logging.getLogger("MAIN")
    logger.info(f"Arguments:\n {args}")
    data_encoder_class = get_data_encoder_class(args.data_encoder)
    data_encoder = data_encoder_class(args)
    data_encoder.create_datasets()


if __name__ == "__main__":
    main()
