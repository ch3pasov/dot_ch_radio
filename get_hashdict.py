from volume.radio import common_tree
from volume.config.tg_ids import bot_username
import hashlib


def stable_hash(string):
    return hashlib.md5(string.encode()).hexdigest()


common_hashdict = {}
root_path_hash = stable_hash("")
to_see = [""]
while to_see:
    beautiful_path = to_see.pop(0)
    path_hash = stable_hash(beautiful_path)

    common_hashdict[path_hash] = {}

    common_hashdict[path_hash]["share"] = f"t.me/{bot_username}?start={path_hash}"

    pointer = common_tree
    for step in beautiful_path.split("/")[1:]:
        content = pointer['children']
        pointer = content[step]

    if "/" in beautiful_path:
        parent_hash = stable_hash(beautiful_path.rsplit("/", 1)[0])
        common_hashdict[path_hash]["parent"] = parent_hash

    if 'children' in pointer:
        children_paths = dict([(f"{beautiful_path}/{child}", pointer['children'][child]['name']) for child in pointer['children']])
        to_see.extend(children_paths.keys())
        children = dict([(stable_hash(f"{beautiful_path}/{child}"), pointer['children'][child]['name']) for child in pointer['children']])
        common_hashdict[path_hash]["children"] = children

    # добавляем обязательный name и необязательные description, radio_url, ...
    for key in pointer:
        if key not in ['children']:
            common_hashdict[path_hash][key] = pointer[key]
