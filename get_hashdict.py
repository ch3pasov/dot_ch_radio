from content.content import common_tree, common_trees
from config.tg_ids import bot_username
from libs.content_index import build_content_index
from libs.i18n import RU, normalize_locale


common_hashdict, alias_dict = build_content_index(common_tree, bot_username)
common_hashdicts = {RU: common_hashdict}
alias_dicts = {RU: alias_dict}

for locale, tree in common_trees.items():
    if locale == RU:
        continue
    common_hashdicts[locale], alias_dicts[locale] = build_content_index(
        tree,
        bot_username,
    )


def content_indexes_for_locale(locale):
    normalized = normalize_locale(locale)
    return common_hashdicts[normalized], alias_dicts[normalized]
