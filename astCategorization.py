import re
import json
from pathlib import Path
import sys

# Repair actions
ADD_PARAM = "ADD_PARAM"
DEL_PARAM = "DEL_PARAM"
CHANGE_TYPE = "CHANGE_TYPE"
MOD_PARAM = "MOD_PARAM"
MOD_MD_CALL = "MOD_MD_CALL"
ADD_THROWS = "ADD_THROWS"
DEL_THROWS = "DEL_THROWS"
INSERT_LINE = "INSERT_LINE"
DEL_LINE = "DEL_LINE"
MOVE = "MOVE"
OTHER = "OTHER"
# Repair categories
ORACLE_CHANGE = "ORACLE_CHANGE"
INVOCATION_CHANGE = "INVOCATION_CHANGE"
PARAM_OR_TYPE_CHANGE = "PARAM_OR_TYPE_CHANGE"
UNKNOWN = "UNKNOWN"


def get_action_text(action):
    node_type = action["nodeType"]
    parents = action["parents"][0]
    if action["nodeType"] == "TypeAccess" and action["parents"][0] == "FieldRead":
        node_type = action["nodeType"] + "," + action["parents"][0]
        parents = action["parents"][1]
    return f"{action['type']}-{node_type}-{parents}"


def parse_constructor_signature(signature):
    full_pattern = r"(.+?)((\.(.+?))*?)\.(.+?)\((.*)\)"
    match = re.search(full_pattern, signature)
    if match:
        groups = match.groups()
        class_name = groups[4].split(".")[-1]
        args_cnt = 0 if groups[5] == "" else len(groups[5].split(","))
        return class_name, args_cnt

    short_pattern = r"(.+?)\((.*)\)"
    match = re.search(short_pattern, signature)
    groups = match.groups()
    class_name = groups[0]
    args_cnt = 0 if groups[1] == "" else len(groups[1].split(","))
    return class_name, args_cnt


def get_action_categories(action, repair_hunk):
    categories = set()
    action_text = get_action_text(action)
    match = re.search("Update-ConstructorCall-(.+)", action_text)
    if match:
        src_class_name, src_arg_cnt = parse_constructor_signature(action["srcNode"]["label"])
        dst_class_name, dst_arg_cnt = parse_constructor_signature(action["dstNode"]["label"])
        if src_class_name != dst_class_name:
            categories.add(INVOCATION_CHANGE)
        else:
            categories.add(PARAM_OR_TYPE_CHANGE)

        # If changing an exception type, assume it's oracle related
        # If the class name used in a line with 'assert', assume it's oracle related
        #       Only if actual class name (based on caps) to avoid hitting a var name (e.g. String vs string)
        if (
            "Exception" in src_class_name
            or "Exception" in dst_class_name
            or (
                "targetChanges" in repair_hunk
                and any(
                    ["assert" in h["line"].lower() and dst_class_name in h["line"] for h in repair_hunk["targetChanges"]]
                )
            )
            or (
                "sourceChanges" in repair_hunk
                and any(
                    ["assert" in h["line"].lower() and src_class_name in h["line"] for h in repair_hunk["sourceChanges"]]
                )
            )
        ):
            categories.add(ORACLE_CHANGE)
    else:
        patterns = {
            ADD_PARAM: r"Insert-(.+)-(ConstructorCall|NewClass|Invocation)",
            DEL_PARAM: r"Delete-(.+)-(ConstructorCall|NewClass|Invocation)",
            CHANGE_TYPE: r"Update-(TypeAccess|TypeAccess,FieldRead|THROWN|VARIABLE_TYPE|TYPE_CASE)-(.+)",
            MOD_PARAM: r"Update-(Literal|FieldRead|VariableRead)-(.+)",
            MOD_MD_CALL: r"Update-Invocation-(.+)",
            ADD_THROWS: r"Insert-(THROWN_TYPES|THROWN)-(Method|THROWN_TYPES)",
            DEL_THROWS: r"Delete-(THROWN_TYPES|THROWN)-(Method|THROWN_TYPES)",
            INSERT_LINE: r"Insert-(Invocation|Assignment|LocalVariable)-(Method|Try|TryWithResource|While|Lambda)",
            DEL_LINE: r"Delete-(Invocation|Assignment|LocalVariable)-(Method|Try|TryWithResource|While)",
            MOVE: r"Move-(.+)-(.+)",
        }
        new_cats = set()
        for key, pattern in patterns.items():
            match = re.search(pattern, action_text)
            if match:
                # Categories for param/type change if not changing an exception
                if key in [ADD_PARAM, DEL_PARAM, MOD_PARAM, MOVE] or (
                    key == CHANGE_TYPE
                    and not (
                        ("dstNode" in action and "Exception" in action["dstNode"]["label"])
                        or ("srcNode" in action and "Exception" in action["srcNode"]["label"])
                    )
                ):
                    new_cats.add(PARAM_OR_TYPE_CHANGE)

                # Categories for invocation change
                elif key in [INSERT_LINE, DEL_LINE, MOD_MD_CALL]:
                    new_cats.add(INVOCATION_CHANGE)

                # Categories for oracle change, or if the change is in a hunk with an assert statement, or changing the type of an exception
                if (
                    key in [ADD_THROWS, DEL_THROWS]
                    or (
                        "srcNode" in action
                        and "sourceChanges" in repair_hunk
                        and any(
                            [
                                "assert" in h["line"].lower() and action["srcNode"]["label"] in h["line"]
                                for h in repair_hunk["sourceChanges"]
                            ]
                        )
                    )
                    or (
                        "dstNode" in action
                        and "targetChanges" in repair_hunk
                        and any(
                            [
                                "assert" in h["line"].lower() and action["dstNode"]["label"] in h["line"]
                                for h in repair_hunk["targetChanges"]
                            ]
                        )
                    )
                    or (
                        key == CHANGE_TYPE
                        and (
                            ("dstNode" in action and "Exception" in action["dstNode"]["label"])
                            or ("srcNode" in action and "Exception" in action["srcNode"]["label"])
                        )
                    )
                ):
                    # If changing which assert method is used then it's not an oracle change
                    if key != MOD_MD_CALL or (
                        ("dstNode" in action and not "assert" in action["dstNode"]["label"])
                        and ("srcNode" in action and not "assert" in action["srcNode"]["label"])
                    ):
                        new_cats = {
                            ORACLE_CHANGE,
                        }
        categories.update(new_cats)
    return sorted(list(categories))


def get_repair_categories(test_repair):
    repair_categories = set()
    for action in test_repair["astActions"]:
        repair_categories.update(get_action_categories(action, test_repair["hunk"]))
    repair_categories = tuple(sorted(list(repair_categories)))
    if len(repair_categories) == 0:
        repair_categories = (UNKNOWN,)
    return repair_categories


def main():
    if len(sys.argv) <= 1:
        print("No arguments provided! Usage: python repair_catg.py [dataset_dir]")

    ds_path = Path(sys.argv[1])
    dataset = []
    for project_ds_path in ds_path.rglob("dataset.json"):
        dataset.extend(json.loads(project_ds_path.read_text()))
    print(f"Read {len(dataset)} test repairs")

    repair_cat = {}
    for test_repair in dataset:
        item = {"categories": get_repair_categories(test_repair), "astActions": len(test_repair["astActions"])}
        repair_cat[test_repair["ID"]] = item

    (ds_path / "repair_categories.json").write_text(json.dumps(repair_cat, indent=2, sort_keys=False))
    print(f"Finished")


if __name__ == "__main__":
    main()
