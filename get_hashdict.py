from volume.content import common_tree
from volume.config.tg_ids import bot_username
import hashlib


def stable_hash(string):
    return hashlib.md5(string.encode()).hexdigest()


children_params = ["url", "beta_access"]
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

    pointer = common_tree
    for step in beautiful_path.split("/")[1:]:
        content = pointer['children']
        pointer = content[step]

    if "/" in beautiful_path:
        parent_hash = stable_hash(beautiful_path.rsplit("/", 1)[0])
        common_hashdict[path_hash]["parent"] = parent_hash

    common_hashdict[path_hash]["share"] = f"t.me/{bot_username}?start=id={path_hash}"
    if "alias" in pointer:
        alias = pointer["alias"]
        alias_dict[alias] = path_hash
        common_hashdict[path_hash]["share"] = f"t.me/{bot_username}?start={alias}"

    if 'children' in pointer:
        children_paths = dict([(f"{beautiful_path}/{child}", pointer['children'][child]['name']) for child in pointer['children']])
        inherit_to_children = inherited.copy()
        for inherited_param in inherited_params:
            if inherited_param in pointer:
                inherit_to_children[inherited_param] = pointer[inherited_param]

        to_see.extend([{"path": key, "inherited": inherit_to_children} for key in children_paths.keys()])
        children_dict = {}
        for child in pointer['children']:
            child_hash = stable_hash(f"{beautiful_path}/{child}")
            children_dict[child_hash] = {
                "name": pointer['children'][child]['name']
            }

            for inherited_children_param in list(set(inherited_params) & set(children_params)):
                if inherited_children_param in inherited:
                    children_dict[child_hash][inherited_children_param] = inherited[inherited_children_param]
                if inherited_children_param in pointer:
                    children_dict[child_hash][inherited_children_param] = pointer[inherited_children_param]
            for children_param in children_params:
                if children_param in pointer['children'][child]:
                    children_dict[child_hash][children_param] = pointer['children'][child][children_param]
        common_hashdict[path_hash]["children"] = children_dict

    # добавляем обязательный name и необязательные description, radio_url, ...
    for key in pointer:
        if key not in ['children']:
            common_hashdict[path_hash][key] = pointer[key]
