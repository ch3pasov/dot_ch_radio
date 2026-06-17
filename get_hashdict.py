from volume.content import common_tree
from volume.config.tg_ids import bot_username
import hashlib


def stable_hash(string):
    return hashlib.md5(string.encode()).hexdigest()


children_params = [
    "url",
    "radio_url",
    "beta_access",
    "switch_inline_query",
    "switch_inline_query_current_chat",
    "button_text",
    "button_style",
    "button_icon",
    "button_type",
    "copy_text",
    "web_app_url",
    "simple_web_app_url",
    "user_id",
    "same_peer",
    "row",
    "break_before",
    "break_after",
]
inherited_params = ["beta_access"]

common_hashdict = {}
alias_dict = {}

to_see = [{"path": "", "inherited": {}}]
while to_see:
    to_see_now = to_see.pop(0)
    beautiful_path = to_see_now["path"]
    path_hash = stable_hash(beautiful_path)

    inherited = to_see_now["inherited"]
    common_hashdict[path_hash] = inherited.copy()
    common_hashdict[path_hash]["path"] = beautiful_path

    pointer = common_tree
    for step in beautiful_path.split("/")[1:]:
        content = pointer["children"]
        pointer = content[step]

    if "/" in beautiful_path:
        parent_hash = stable_hash(beautiful_path.rsplit("/", 1)[0])
        common_hashdict[path_hash]["parent"] = parent_hash

    common_hashdict[path_hash]["share"] = f"t.me/{bot_username}?start=id={path_hash}"
    if "alias" in pointer:
        alias = pointer["alias"]
        alias_dict[alias] = path_hash
        common_hashdict[path_hash]["share"] = f"t.me/{bot_username}?start={alias}"

    if "children" in pointer:
        inherit_to_children = inherited.copy()
        for inherited_param in inherited_params:
            if inherited_param in pointer:
                inherit_to_children[inherited_param] = pointer[inherited_param]

        children_dict = {}
        for child_key, child_node in pointer["children"].items():
            child_path = f"{beautiful_path}/{child_key}"
            child_hash = stable_hash(child_path)
            to_see.append({"path": child_path, "inherited": inherit_to_children})

            child_summary = {"name": child_node["name"]}
            for inherited_children_param in list(set(inherited_params) & set(children_params)):
                if inherited_children_param in inherited:
                    child_summary[inherited_children_param] = inherited[inherited_children_param]
                if inherited_children_param in pointer:
                    child_summary[inherited_children_param] = pointer[inherited_children_param]
            for children_param in children_params:
                if children_param in child_node:
                    child_summary[children_param] = child_node[children_param]
            children_dict[child_hash] = child_summary

        common_hashdict[path_hash]["children"] = children_dict

    # добавляем обязательный name и необязательные description, radio_url, ...
    for key in pointer:
        if key != "children":
            common_hashdict[path_hash][key] = pointer[key]
