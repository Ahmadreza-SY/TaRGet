from torch.utils.data import RandomSampler, DataLoader, SequentialSampler
from torch.utils.data.distributed import DistributedSampler
from DES import DistributedEvalSampler
import json


def create_loader(dataset, args, eval_mode=False, seq=False):
    if eval_mode:
        if args.world_size == 1 or seq:
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


def save_stats(args):
    if args.rank == 0:
        with open(str(args.output_dir / "stats.json"), "w") as f:
            f.write(json.dumps(args.stats, indent=2, sort_keys=False))
