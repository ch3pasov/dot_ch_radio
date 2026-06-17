"""Telegram file_id support for rich content nodes."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Mapping

BUCKET_URL_RE = re.compile(r"https://storage\.yandexcloud\.net/dot-ch-bot-bucket/[^)\]\"\s]+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\((https://storage\.yandexcloud\.net/dot-ch-bot-bucket/[^)]+)\)")
INVISIBLE_CHARS = {"​", "‌", "‍", "⁠", "﻿", "͏", "⠀"}


def apply_telegram_file_ids(tree: Mapping, file_ids: Mapping[str, str]) -> dict:
    normalized = deepcopy(dict(tree))
    if file_ids:
        _apply_to_node(normalized, file_ids)
    return normalized


def _apply_to_node(node: dict, file_ids: Mapping[str, str]) -> None:
    description = node.get("description")
    if isinstance(description, str):
        urls = BUCKET_URL_RE.findall(description)
        matched_urls = [url for url in urls if url in file_ids]
        if matched_urls:
            node.setdefault("telegram_file_id", file_ids[matched_urls[0]])
            node["description"] = _clean_bucket_links(description, file_ids)

    children = node.get("children", {})
    iterable = children.values() if isinstance(children, dict) else children
    for child in iterable:
        if isinstance(child, dict):
            _apply_to_node(child, file_ids)


def _is_invisible_label(label: str) -> bool:
    stripped = "".join(ch for ch in label if ch not in INVISIBLE_CHARS).strip()
    return stripped == ""


def _clean_bucket_links(description: str, file_ids: Mapping[str, str]) -> str:
    def replace_markdown_link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if url not in file_ids:
            return match.group(0)
        if _is_invisible_label(label):
            return ""
        return label

    cleaned = MARKDOWN_LINK_RE.sub(replace_markdown_link, description)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
