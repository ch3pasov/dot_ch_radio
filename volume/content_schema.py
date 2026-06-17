"""Small helpers for building the bot content tree.

The renderer still accepts the old plain-dict shape. These helpers add a more
compact DSL for new file-tree nodes and normalize list-based children into the
existing dict-based tree used by get_hashdict.py.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Iterable, Mapping

BUTTON_STYLES = {"primary", "danger", "success"}


def node(name: str, *, id: str | None = None, children: Any = None, **params: Any) -> dict[str, Any]:
    item = {"name": name, **params}
    if id is not None:
        item["id"] = id
    if children is not None:
        item["children"] = children
    return item


def folder(name: str, *, id: str | None = None, children: Any = None, **params: Any) -> dict[str, Any]:
    return node(name, id=id, children=children or [], **params)


def link(name: str, url: str, *, id: str | None = None, **params: Any) -> dict[str, Any]:
    return node(name, id=id, url=url, **params)


def copy_button(name: str, copy_text: str, *, id: str | None = None, **params: Any) -> dict[str, Any]:
    return node(name, id=id, button_type="copy", copy_text=copy_text, **params)


def web_app(name: str, url: str, *, id: str | None = None, simple: bool = False, **params: Any) -> dict[str, Any]:
    key = "simple_web_app_url" if simple else "web_app_url"
    return node(name, id=id, **{key: url}, **params)


def user_profile(name: str, user_id: int, *, id: str | None = None, **params: Any) -> dict[str, Any]:
    return node(name, id=id, button_type="user_profile", user_id=user_id, **params)


def validate_button_style(style: str | None) -> str | None:
    if style is None:
        return None
    normalized = style.lower()
    if normalized not in BUTTON_STYLES:
        raise ValueError(f"Unknown button_style {style!r}; expected one of {sorted(BUTTON_STYLES)}")
    return normalized


def normalize_tree(tree: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(tree))
    _normalize_node(normalized)
    return normalized


def _normalize_node(item: dict[str, Any]) -> None:
    if "button_color" in item and "button_style" not in item:
        item["button_style"] = item.pop("button_color")
    if "custom_emoji_id" in item and "button_icon" not in item:
        item["button_icon"] = item.pop("custom_emoji_id")
    if "button_style" in item:
        item["button_style"] = validate_button_style(item["button_style"])
    if "children" in item:
        item["children"] = normalize_children(item["children"])


def normalize_children(children: Any) -> OrderedDict[str, dict[str, Any]]:
    if isinstance(children, Mapping):
        iterable: Iterable[tuple[str, Any]] = children.items()
    else:
        iterable = []
        for child in children:
            if not isinstance(child, Mapping):
                raise TypeError(f"List children must be mappings, got {type(child).__name__}")
            if "id" not in child:
                raise ValueError(f"List child {child.get('name', child)!r} must define id")
            iterable.append((str(child["id"]), child))

    normalized: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for key, raw_child in iterable:
        child = deepcopy(dict(raw_child))
        child.pop("id", None)
        _normalize_node(child)
        normalized[str(key)] = child
    return normalized
