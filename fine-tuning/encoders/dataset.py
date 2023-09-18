import torch


class ATRDataset(torch.utils.data.Dataset):
    def __init__(self, ds, tokenizer, split, args):
        self.data = []
        self.max_length = args.max_length
        self.tokenizer = tokenizer
        valid_length_ind = set()
        for i, row in ds.iterrows():
            input = self.get_input(row)
            output = self.get_output(row)
            input = self.tokenizer.encode(input, return_tensors="pt")
            output = self.tokenizer.encode(output, return_tensors="pt")
            if not self.has_valid_length(input, output):
                continue
            self.data.append(self.create_item(input, output))
            valid_length_ind.add(i)

        ds = ds.iloc[list(valid_length_ind)].reset_index(drop=True)
        ds_output_dir = args.output_dir / "splits" / f"{split}.json"
        ds.to_json(ds_output_dir, orient="records", indent=2)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def get_input(self, row):
        pass

    def get_output(self, row):
        pass

    def create_item(self, input, output):
        pass

    def has_valid_length(self, input, output):
        pass

# TODO add model encoders and collate_fn
class EncDecDataset(ATRDataset):
    def get_input(self, row):
        return row["input"]

    def get_output(self, row):
        return row["output"] + self.tokenizer.eos_token

    def create_item(self, input, output):
        return {"input_ids": input, "labels": output, "attention_mask": torch.ones(input.size()).long()}

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length and output.size(1) <= self.max_length


class DecoderDataset(ATRDataset):
    def get_input(self, row):
        return row["input"] + row["output"] + self.tokenizer.eos_token

    def get_output(self, row):
        return row["output"] + self.tokenizer.eos_token

    def create_item(self, input, output):
        return {
            "input_ids": input,
            "labels": torch.cat([torch.zeros(1, input.size(1) - output.size(1)).fill_(-100).long(), output]),
            "attention_mask": torch.ones(input.size()).long(),
        }

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length
