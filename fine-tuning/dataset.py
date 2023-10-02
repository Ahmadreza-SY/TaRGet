import torch


# Since this class is pickled, only the data-related stuff is saved in self
class ATRDataset(torch.utils.data.Dataset):
    def __init__(self, ds, tokenizer, split, args):
        self.initialize_tokens(tokenizer)
        self.data = []
        self.max_length = args.max_length
        valid_length_ind = set()
        for i, row in ds.iterrows():
            input = self.get_input(row, tokenizer)
            output = self.get_output(row, tokenizer)
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

    def get_input(self, row, tokenizer):
        pass

    def get_inference_input(self, row, tokenizer):
        return self.get_input(row, tokenizer)

    def get_output(self, row, tokenizer):
        pass

    def create_item(self, input, output):
        pass

    def has_valid_length(self, input, output):
        pass

    def get_pad_eos_for_generation(self, tokenizer):
        return None, None

    def get_decoder_start_token_id(self, tokenizer):
        return None

    def get_new_generated_tokens(self, outputs, input_ids):
        return outputs

    @staticmethod
    def get_max_input_len(max_len):
        pass


class EncDecDataset(ATRDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.pad_id = tokenizer.convert_tokens_to_ids(tokenizer.special_tokens_map["pad_token"])

    def get_input(self, row, tokenizer):
        input = row["input"]
        return tokenizer.encode(input, return_tensors="pt")

    def get_output(self, row, tokenizer):
        output = row["output"]
        return tokenizer.encode(output, return_tensors="pt")

    def create_item(self, input, output):
        return {"input_ids": input, "labels": output, "attention_mask": torch.ones(input.size()).long()}

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length and output.size(1) <= self.max_length

    @staticmethod
    def get_max_input_len(max_len):
        return max_len


class PLBARTDataset(EncDecDataset):
    def get_input(self, row, tokenizer):
        input = row["input"] + tokenizer.eos_token + "__java__"
        return tokenizer.encode(input, add_special_tokens=False, return_tensors="pt")

    def get_output(self, row, tokenizer):
        output = "__java__" + row["output"] + tokenizer.eos_token
        return tokenizer.encode(output, add_special_tokens=False, return_tensors="pt")

    def get_decoder_start_token_id(self, tokenizer):
        return tokenizer.lang_code_to_id["__java__"]


class DecoderDataset(ATRDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.eos_token = tokenizer.eos_token

    def get_input(self, row, tokenizer):
        input = row["input"] + row["output"] + self.eos_token
        return tokenizer.encode(input, return_tensors="pt")

    def get_inference_input(self, row, tokenizer):
        return tokenizer.encode(row["input"], return_tensors="pt")

    def get_output(self, row, tokenizer):
        output = row["output"] + self.eos_token
        return tokenizer.encode(output, return_tensors="pt")

    def create_item(self, input, output):
        return {
            "input_ids": input,
            "labels": torch.cat([torch.zeros(1, input.size(1) - output.size(1)).fill_(-100).long(), output], dim=1),
            "attention_mask": torch.ones(input.size()).long(),
        }

    def has_valid_length(self, input, output):
        return input.size(1) <= self.max_length

    def get_pad_eos_for_generation(self, tokenizer):
        return self.pad_id, tokenizer.convert_tokens_to_ids(self.eos_token)

    def get_new_generated_tokens(self, outputs, input_ids):
        new_tokens_start = input_ids.size(1)
        return outputs[:, new_tokens_start:]

    @staticmethod
    def get_max_input_len(max_len):
        # When decoder-only, we consider two-third of the prompt as the input, and the rest as the output.
        return max_len * 2 // 3


class CodeGenDataset(DecoderDataset):
    def initialize_tokens(self, tokenizer):
        super().initialize_tokens(tokenizer)
        self.pad_id = tokenizer.eos_token_id
