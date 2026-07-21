"""Build the bot's stateless path, hash and alias indexes."""

from __future__ import annotations

import hashlib
from collections import deque
from typing import Any, Mapping


CHILD_SUMMARY_FIELDS = (
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
    "callback_data",
    "message_effects",
    "same_peer",
    "row",
    "break_before",
    "break_after",
)
INHERITED_FIELDS = ("beta_access",)


def stable_hash(value: str) -> str:
    return hashlib.md5(value.encode(), usedforsecurity=False).hexdigest()


def build_content_index(
    tree: Mapping[str, Any],
    bot_username: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Index a normalized content tree by MD5(current path) and alias.

    Paths are rebuilt from the tree on every import. Moving a node therefore
    intentionally changes its hash; there are no redirects or persisted user
    navigation records.
    """

    hash_index: dict[str, dict[str, Any]] = {}
    alias_index: dict[str, str] = {}
    hash_paths: dict[str, str] = {}
    pending = deque([("", tree, {})])

    while pending:
        path, item, inherited = pending.popleft()
        path_hash = stable_hash(path)
        previous_path = hash_paths.get(path_hash)
        if previous_path is not None and previous_path != path:
            raise ValueError(
                f"Content path hash collision: {previous_path!r} and {path!r}"
            )
        hash_paths[path_hash] = path

        indexed = dict(inherited)
        indexed["path"] = path
        if "/" in path:
            indexed["parent"] = stable_hash(path.rsplit("/", 1)[0])

        indexed["share"] = f"t.me/{bot_username}?start=id={path_hash}"
        alias = item.get("alias")
        if alias is not None:
            alias = str(alias)
            previous_hash = alias_index.get(alias)
            if previous_hash is not None and previous_hash != path_hash:
                raise ValueError(f"Duplicate content alias: {alias!r}")
            alias_index[alias] = path_hash
            indexed["share"] = f"t.me/{bot_username}?start={alias}"

        children = item.get("children")
        if children is not None:
            inherited_for_children = dict(inherited)
            for field in INHERITED_FIELDS:
                if field in item:
                    inherited_for_children[field] = item[field]

            child_summaries: dict[str, dict[str, Any]] = {}
            for child_key, child in children.items():
                child_path = f"{path}/{child_key}"
                child_hash = stable_hash(child_path)
                pending.append((child_path, child, inherited_for_children))

                summary = {"name": child["name"]}
                for field in INHERITED_FIELDS:
                    if field in inherited:
                        summary[field] = inherited[field]
                    if field in item:
                        summary[field] = item[field]
                for field in CHILD_SUMMARY_FIELDS:
                    if field in child:
                        summary[field] = child[field]
                child_summaries[child_hash] = summary

            indexed["children"] = child_summaries

        for key, value in item.items():
            if key != "children":
                indexed[key] = value
        hash_index[path_hash] = indexed

    for item_hash, item in hash_index.items():
        parent_hash = item.get("parent")
        if parent_hash is not None and parent_hash not in hash_index:
            raise ValueError(
                f"Missing parent {parent_hash!r} for content node {item_hash!r}"
            )

    return hash_index, alias_index
