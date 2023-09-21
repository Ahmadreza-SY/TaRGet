import torch


# Since this class is pickled, only the data-related stuff is saved in self
class ATRDataset(torch.utils.data.Dataset):
    def __init__(self, ds, tokenizer, split, args):
        self.initialize_tokens(tokenizer)
        self.data = []
        self.max_length = args.max_length
        valid_length_ind = set()
        for i, row in ds.iterrows():
            input = self.get_input(row)
            output = self.get_output(row)
            input = tokenizer.encode(input, return_tensors="pt")
            output = tokenizer.encode(output, return_tensors="pt")
            if not self.has_valid_length(input, output):
                continue
            self.data.append(self.create_item(input, output))
            valid_length_ind.add(i)

        ds = ds.iloc[list(valid_length_ind)].reset_index(drop=True)
        ds_output_dir = args.output_dir / "splits"
        ds_output_dir.mkdir(exist_ok=True, parents=True)
        ds.to_json(ds_output_dir / f"{split}.json", orient="records", indent=2)

    def __len__(self):
        return len(self.data)

    def __getitem__(self, item):
        return self.data[item]

    def initialize_tokens(self, tokenizer):
        pass

    def get_input(self, row):
        pass

    def get_output(self, row):
        pass

    def create_item(self, input, output):
        pass

    def has_valid_length(self, input, output):
        pass


class EncDecDataset(ATRDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.pad_id = tokenizer.convert_tokens_to_ids(tokenizer.special_tokens_map["pad_token"])

    def get_input(self, row):
        return row["input"]

    def get_output(self, row):
        return row["output"]

    def create_item(self, input, output):
        return {"input_ids": input, "labels": output, "attention_mask": torch.ones(input.size()).long()}

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length and output.size(1) <= self.max_length


class DecoderDataset(ATRDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.eos_token = tokenizer.eos_token

    def get_input(self, row):
        return row["input"] + row["output"] + self.eos_token

    def get_output(self, row):
        return row["output"] + self.eos_token

    def create_item(self, input, output):
        return {
            "input_ids": input,
            "labels": torch.cat([torch.zeros(1, input.size(1) - output.size(1)).fill_(-100).long(), output], dim=1),
            "attention_mask": torch.ones(input.size()).long(),
        }

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length


class CodeGenDataset(DecoderDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.pad_id = tokenizer.eos_token_id


class IncoderDataset(DecoderDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.pad_id = tokenizer.convert_tokens_to_ids("<|endofmask|>")

    def get_input(self, row):
        return row["input"] + row["output"] + "<|endofmask|>"

    def get_output(self, row):
        return row["output"] + "<|endofmask|>"
