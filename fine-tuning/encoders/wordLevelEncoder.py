from encoders.simOrderEncoder import SimOrderDataEncoder
from encoders.preprocessing.textDiff import get_hunk_diffs
from diff_match_patch import diff_match_patch as dmp
from encoders.abstractEncoder import Tokens


class WordLevelTokens(Tokens):
    DELETE_END = "[</DEL>]"
    ADD_END = "[</ADD>]"


class WordLevelDataEncoder(SimOrderDataEncoder):
    def get_special_tokens_class(self):
        return WordLevelTokens

    def create_hunk_document(self, hunk):
        diffs = get_hunk_diffs(hunk)
        annotated_body = []
        for type, text in diffs:
            text = text.strip()
            if type == dmp.DIFF_EQUAL:
                annotated_body.append(text)
            elif type == dmp.DIFF_DELETE:
                annotated_body.extend([Tokens.DELETE, text, WordLevelTokens.DELETE_END])
            elif type == dmp.DIFF_INSERT:
                annotated_body.extend([Tokens.ADD, text, WordLevelTokens.ADD_END])
        annotated_doc = "".join([Tokens.HUNK] + annotated_body + [Tokens.HUNK_END])

        return annotated_doc
