from encoders.abstractEncoder import AbstractDataEncoder, Tokens

class NoContextTokens:
    BREAKAGE_START = Tokens.BREAKAGE_START
    BREAKAGE_END = Tokens.BREAKAGE_END

class NoContextDataEncoder(AbstractDataEncoder):
    def get_special_tokens_class(self):
        return NoContextTokens
    
    def prioritize_changed_documents(self, row):
        return [{"annotated_doc": "EMPTY", "annotated_doc_seq": [-1]}]
    
    def create_input(self, test_context, changed_docs):
        return test_context