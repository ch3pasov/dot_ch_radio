"""Telegram asset index support for rich content nodes."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

ASSET_INDEX_PATH = Path(__file__).resolve().parent / "telegram_assets.json"
BUCKET_URL_RE = re.compile(r"https://storage\.yandexcloud\.net/dot-ch-bot-bucket/[^)\]\"\s]+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\((https://storage\.yandexcloud\.net/dot-ch-bot-bucket/[^)]+)\)")
INVISIBLE_CHARS = {"​", "‌", "‍", "⁠", "﻿", "͏", "⠀"}


def load_telegram_assets() -> dict[str, Any]:
    if not ASSET_INDEX_PATH.exists():
        return {"assets": {}}
    return json.loads(ASSET_INDEX_PATH.read_text(encoding="utf-8"))


def apply_telegram_assets(tree: Mapping[str, Any]) -> dict[str, Any]:
    assets = load_telegram_assets().get("assets", {})
    normalized = deepcopy(dict(tree))
    if not assets:
        return normalized
    _apply_to_node(normalized, assets)
    return normalized


def _apply_to_node(node: dict[str, Any], assets: dict[str, Any]) -> None:
    description = node.get("description")
    if isinstance(description, str):
        urls = BUCKET_URL_RE.findall(description)
        telegram_assets = [
            {"source_url": url, **assets[url]}
            for url in urls
            if url in assets
        ]
        if telegram_assets:
            node.setdefault("telegram_assets", telegram_assets)
            node.setdefault("telegram_media", telegram_assets[0])
            node["description"] = _clean_bucket_links(description, assets)

    for child in node.get("children", {}).values() if isinstance(node.get("children"), dict) else node.get("children", []):
        if isinstance(child, dict):
            _apply_to_node(child, assets)


def _is_invisible_label(label: str) -> bool:
    stripped = "".join(ch for ch in label if ch not in INVISIBLE_CHARS).strip()
    return stripped == ""


def _clean_bucket_links(description: str, assets: dict[str, Any]) -> str:
    def replace_markdown_link(match: re.Match[str]) -> str:
        label, url = match.group(1), match.group(2)
        if url not in assets:
            return match.group(0)
        if _is_invisible_label(label):
            return ""
        return label

    cleaned = MARKDOWN_LINK_RE.sub(replace_markdown_link, description)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
