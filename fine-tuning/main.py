import sys

sys.path.append("../common")
from pathlib import Path
from transformers import PLBartForConditionalGeneration, PLBartTokenizer
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
    parser.add_argument("-d", "--dataset_dir", required=True, type=str)
    parser.add_argument("-de", "--data_encoder", required=True, type=str)
    parser.add_argument("-sc", "--scoring", default="em", type=str, choices=["bleu", "em"])
    parser.add_argument("-b", "--batch_size", required=True, type=int)
    parser.add_argument("-e", "--epochs", required=True, type=int)
    parser.add_argument("-m", "--max_seq", required=True, type=int)
    parser.add_argument("-ebs", "--eval_batch_size", default=16, type=int)
    parser.add_argument("-c", "--checkpoint_interval", default=2, type=int)
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

    parser.add_argument("-mpr", "--multi_predict_rounds", default=1, type=int)
    parser.add_argument("-sri", "--subsequent_round_inputs", default=10, type=int)

    logger = logging.getLogger("MAIN")

    args = parser.parse_args()
    args.output_dir = Path(args.output_dir)
    args.world_size = args.gpus * args.nodes
    args.model_name_or_path = "uclanlp/plbart-base"
    args.model_class = PLBartForConditionalGeneration
    args.model_tokenizer_class = PLBartTokenizer
    try:
        args.data_encoder_class = getattr(sys.modules[__name__], args.data_encoder + "DataEncoder")
    except AttributeError:
        print(f"Invalid data encoder '{args.data_encoder}'")
        sys.exit()

    load_data(args)

    mp.spawn(run, nprocs=args.gpus, args=(args,))

    logger.info("All jobs done!")


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

    torch.cuda.set_device(gpu)

    if not args.test_only:
        train(gpu, args)

    test(gpu, args)


def load_data(args):
    data_encoder = args.data_encoder_class(args)
    dataset_splits = list(data_encoder.load_dataset())
    args.train_dataset, args.valid_dataset, args.test_dataset = dataset_splits
    args.data_encoder_instance = data_encoder
    args.tokenizer = data_encoder.tokenizer
    if (args.output_dir / "stats.json").exists():
        with open(str(args.output_dir / "stats.json")) as f:
            args.stats = json.load(f)


if __name__ == "__main__":
    main()
