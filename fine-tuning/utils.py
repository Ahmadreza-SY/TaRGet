import json
import torch
from torch.utils.data import SequentialSampler, DataLoader
from torch.utils.data.distributed import DistributedSampler
from DES import DistributedEvalSampler
import sys
from encoders import *


def create_loader(dataset, args, valid_mode=False):
    def custom_collate(batch):
        batch_data = {"input_ids": [], "labels": [], "attention_mask": []}
        max_input_len = max([b["input_ids"].size(1) for b in batch])
        max_output_len = max([b["labels"].size(1) for b in batch])
        for b in batch:
            batch_data["input_ids"].append(
                torch.cat(
                    [b["input_ids"], torch.zeros(1, max_input_len - b["input_ids"].size(1)).fill_(dataset.pad_id).long()],
                    dim=1,
                )
            )
            batch_data["labels"].append(
                torch.cat([b["labels"], torch.zeros(1, max_output_len - b["labels"].size(1)).fill_(-100).long()], dim=1)
            )
            batch_data["attention_mask"].append(
                torch.cat([b["attention_mask"], torch.zeros(1, max_input_len - b["attention_mask"].size(1))], dim=1)
            )
        batch_data["input_ids"] = torch.cat(batch_data["input_ids"], dim=0)
        batch_data["labels"] = torch.cat(batch_data["labels"], dim=0)
        batch_data["attention_mask"] = torch.cat(batch_data["attention_mask"], dim=0)
        return batch_data

    loader = DataLoader(
        dataset=dataset,
        batch_size=args.batch_size,
        collate_fn=custom_collate,
        shuffle=(not valid_mode),
    )
    return loader


def save_stats(args):
    with open(str(args.output_dir / "stats.json"), "w") as f:
        f.write(json.dumps(args.stats, indent=2, sort_keys=False))


def get_data_encoder_class(data_encoder):
    try:
        data_encoder_class = getattr(sys.modules[__name__], data_encoder + "DataEncoder")
        return data_encoder_class
    except AttributeError:
        print(f"Invalid data encoder '{data_encoder}'")
        sys.exit()
