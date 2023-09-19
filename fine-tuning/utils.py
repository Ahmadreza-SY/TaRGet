import json
import torch
from torch.utils.data import SequentialSampler, DataLoader
from torch.utils.data.distributed import DistributedSampler


def create_loader(dataset, args, valid_mode=False):
    def custom_collate(batch):
        batch_data = {"input_ids": [], "labels": [], "attention_mask": []}
        max_input_len = max([b["input_ids"].size(1) for b in batch])
        for b in batch:
            batch_data["input_ids"].append(
                torch.cat(
                    [b["input_ids"], torch.zeros(1, max_input_len - b["input_ids"].size(1)).fill_(args.pad_id).long()], dim=1
                )
            )
            batch_data["labels"].append(
                torch.cat([b["labels"], torch.zeros(1, max_input_len - b["labels"].size(1)).fill_(-100).long()], dim=1)
            )
            batch_data["attention_mask"].append(
                torch.cat([b["attention_mask"], torch.zeros(1, max_input_len - b["attention_mask"].size(1))], dim=1)
            )
        batch_data["input_ids"] = torch.cat(batch_data["input_ids"], dim=0)
        batch_data["labels"] = torch.cat(batch_data["labels"], dim=0)
        batch_data["attention_mask"] = torch.cat(batch_data["attention_mask"], dim=0)
        return batch_data

    if args.world_size == 1:
        sampler = SequentialSampler(dataset)
    else:
        sampler = DistributedSampler(dataset, num_replicas=args.world_size, rank=args.rank)

    loader = DataLoader(
        dataset=dataset,
        batch_size=3 * args.batch_size if valid_mode else args.batch_size,
        sampler=sampler,
        collate_fn=custom_collate,
        shuffle=False,
        pin_memory=True,
    )
    return loader


def save_stats(args):
    if args.rank == 0:
        with open(str(args.output_dir / "stats.json"), "w") as f:
            f.write(json.dumps(args.stats, indent=2, sort_keys=False))
