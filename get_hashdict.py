from content.content import common_tree
from config.tg_ids import bot_username
from libs.content_index import build_content_index


common_hashdict, alias_dict = build_content_index(common_tree, bot_username)
