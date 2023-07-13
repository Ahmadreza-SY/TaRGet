import re
import uuid

non_word_non_whitespace_non_quote_regex = r'(?!"|\'|\s)[\W]'

def mask_quotes(code):
    mask_dict = dict()
    for s in re.findall(r'".+?"', code):
        id = str(uuid.uuid4()).replace('-', '')
        code = code.replace(s, id)
        mask_dict[id] = s

    for s in re.findall(r'\'.+?\'', code):
        id = str(uuid.uuid4()).replace('-', '')
        code = code.replace(s, id)
        mask_dict[id] = s

    return code, mask_dict

def unmask_quotes(code, mask_dict):
    for id, val in mask_dict.items():
        code = code.replace(id, val)

    return code

def space_wrapped_match_group(code, match):
    return " " + code[match.span()[0]:match.span()[1]] + " "

def add_padding_to_chars(code):
    code, mask_dict = mask_quotes(code)
    new_code = re.sub(non_word_non_whitespace_non_quote_regex, lambda m : space_wrapped_match_group(code, m), code)
    new_code = re.sub(r' {2,}', ' ', new_code)
    new_code = unmask_quotes(new_code, mask_dict)
    return new_code

def format_hunk(hunk):
    for s in hunk['sourceChanges']:
        s['line'] = add_padding_to_chars(s['line'])

    for t in hunk['targetChanges']:
        t['line'] = add_padding_to_chars(t['line'])

    return hunk

def format_covered_changes(covered_changes):
    for change in covered_changes:
        for h in change['hunks']:
            format_hunk(h)

    return covered_changes