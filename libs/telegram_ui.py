"""Build Telethon inline-keyboard objects from declarative button specs."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Mapping
from typing import Any

from telethon import Button
from telethon.tl.types import (
    KeyboardButtonCopy,
    KeyboardButtonSimpleWebView,
    KeyboardButtonUserProfile,
    KeyboardButtonWebView,
)

from libs.content_schema import (
    MAX_BUTTONS_PER_MARKUP,
    MAX_BUTTONS_PER_ROW,
    normalize_button_spec,
    validate_callback_data,
    validate_children_columns,
)


_ACTION_FIELDS = (
    "url",
    "copy_text",
    "web_app_url",
    "simple_web_app_url",
    "callback_data",
    "user_id",
    "switch_inline_query",
    "switch_inline_query_current_chat",
)


_ZERO_WIDTH_JOINER = "\u200d"
_KEYCAP = "\u20e3"
_EMOJI_PUNCTUATION_BASES = frozenset({"\u203c", "\u2049", "\u3030", "\u303d"})


def _is_variation_selector(character: str) -> bool:
    codepoint = ord(character)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def _is_emoji_modifier(character: str) -> bool:
    return 0x1F3FB <= ord(character) <= 0x1F3FF


def _is_regional_indicator(character: str) -> bool:
    return 0x1F1E6 <= ord(character) <= 0x1F1FF


def _is_emoji_tag(character: str) -> bool:
    return 0xE0020 <= ord(character) <= 0xE007F


def _is_symbol_base(character: str) -> bool:
    return (
        unicodedata.category(character).startswith("S")
        or character in _EMOJI_PUNCTUATION_BASES
    )


def _consume_cluster_extensions(label: str, position: int) -> int:
    while position < len(label):
        character = label[position]
        if (
            _is_variation_selector(character)
            or unicodedata.category(character).startswith("M")
            or _is_emoji_modifier(character)
            or _is_emoji_tag(character)
        ):
            position += 1
            continue
        if character == _ZERO_WIDTH_JOINER and position + 1 < len(label):
            next_character = label[position + 1]
            if _is_symbol_base(next_character):
                position += 2
                continue
        break
    return position


def _strip_leading_symbol_cluster(label: str) -> str:
    """Strip one leading emoji/symbol grapheme when whitespace follows it."""

    if not label:
        return label

    first = label[0]
    position = 0
    if first in "#*0123456789":
        # Digits, # and * are emoji only when they form a keycap sequence.
        position = 1
        while position < len(label) and _is_variation_selector(label[position]):
            position += 1
        if position >= len(label) or label[position] != _KEYCAP:
            return label
        position += 1
    elif _is_regional_indicator(first):
        # A flag is one grapheme made from two regional indicators.
        position = 1
        if position < len(label) and _is_regional_indicator(label[position]):
            position += 1
    elif _is_symbol_base(first):
        position = 1
    else:
        return label

    position = _consume_cluster_extensions(label, position)
    if position >= len(label) or not label[position].isspace():
        return label
    return label[position:].lstrip()


def _button_label(spec: Mapping[str, Any]) -> str:
    has_explicit_override = "button_text" in spec
    if has_explicit_override:
        label = spec["button_text"]
    else:
        label = spec.get("text") or spec.get("name")
    if not isinstance(label, str) or not label:
        raise ValueError("Button must define a non-empty name, text, or button_text")
    if spec.get("button_icon") is not None and not has_explicit_override:
        label = _strip_leading_symbol_cluster(label)
        if not label:
            raise ValueError("Button label must contain text after its leading emoji/symbol")
    return label


def _button_icon(spec: Mapping[str, Any]) -> int | None:
    icon = spec.get("button_icon")
    return int(icon) if icon is not None else None


def _raw_button_style(spec: Mapping[str, Any]):
    # Telethon 1.43.2 uses the same style object internally for its helpers and
    # raw keyboard-button constructors.  Keeping this in one place prevents
    # renderer-specific style implementations from drifting apart.
    return Button._get_style(spec.get("button_style"), _button_icon(spec))


def _require_string(spec: Mapping[str, Any], field: str) -> str:
    value = spec[field]
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a string")
    return value


def build_button(
    spec: Mapping[str, Any],
    *,
    default_callback_data: str | bytes | None = None,
    default_url: str | None = None,
):
    """Build one Telethon button.

    Content children normally rely on ``default_callback_data`` for their
    generated ``id=<hash>`` route.  Navigation specs similarly provide only
    presentation data and receive a dynamic callback or share URL here.
    Explicit action fields in ``spec`` always take precedence.
    """

    item = normalize_button_spec(spec, allow_message_effects=True)
    label = _button_label(item)
    style = item.get("button_style")
    icon = _button_icon(item)
    explicit_targets = [field for field in _ACTION_FIELDS if field in item]

    if explicit_targets and (default_callback_data is not None or default_url is not None):
        # Defaults are intentionally ignored for explicit actions.  This is
        # how one child collection can contain both folders and URL/actions.
        default_callback_data = None
        default_url = None
    elif default_callback_data is not None and default_url is not None:
        raise ValueError("A button cannot have both a default callback and default URL")

    if "url" in item:
        return Button.url(label, _require_string(item, "url"), style=style, icon=icon)
    if "copy_text" in item:
        return KeyboardButtonCopy(label, _require_string(item, "copy_text"), style=_raw_button_style(item))
    if "web_app_url" in item:
        return KeyboardButtonWebView(label, _require_string(item, "web_app_url"), style=_raw_button_style(item))
    if "simple_web_app_url" in item:
        return KeyboardButtonSimpleWebView(
            label,
            _require_string(item, "simple_web_app_url"),
            style=_raw_button_style(item),
        )
    if "callback_data" in item:
        return Button.inline(label, data=validate_callback_data(item["callback_data"]), style=style, icon=icon)
    if "user_id" in item or item.get("button_type") == "user_profile":
        user_id = item.get("user_id")
        if isinstance(user_id, bool) or not isinstance(user_id, int):
            raise TypeError("user_id must be an integer")
        return KeyboardButtonUserProfile(label, user_id, style=_raw_button_style(item))
    if "switch_inline_query_current_chat" in item:
        return Button.switch_inline(
            label,
            query=_require_string(item, "switch_inline_query_current_chat"),
            same_peer=True,
            style=style,
            icon=icon,
        )
    if "switch_inline_query" in item:
        return Button.switch_inline(
            label,
            query=_require_string(item, "switch_inline_query"),
            same_peer=bool(item.get("same_peer", False)),
            style=style,
            icon=icon,
        )
    if default_callback_data is not None:
        return Button.inline(
            label,
            data=validate_callback_data(default_callback_data),
            style=style,
            icon=icon,
        )
    if default_url is not None:
        if not isinstance(default_url, str):
            raise TypeError("default_url must be a string")
        return Button.url(label, default_url, style=style, icon=icon)
    raise ValueError("Button has no Telegram action target and no runtime default")


def _validate_built_rows(rows: list[list[Any]]) -> list[list[Any]]:
    total = 0
    for row_number, row in enumerate(rows, start=1):
        if not row:
            raise ValueError(f"Button row {row_number} must not be empty")
        if len(row) > MAX_BUTTONS_PER_ROW:
            raise ValueError(f"Button row {row_number} exceeds Telegram's {MAX_BUTTONS_PER_ROW}-button limit")
        total += len(row)
    if total > MAX_BUTTONS_PER_MARKUP:
        raise ValueError(f"Markup exceeds Telegram's {MAX_BUTTONS_PER_MARKUP}-button limit")
    return rows


def build_child_rows(
    children: Mapping[str, Mapping[str, Any]],
    *,
    columns: int = 1,
    callback_data_for: Callable[[str, Mapping[str, Any]], str | bytes] | None = None,
    include: Callable[[str, Mapping[str, Any]], bool] | None = None,
) -> list[list[Any]]:
    """Render ordered content children while respecting declarative breaks."""

    column_count = validate_children_columns(columns)
    callback_factory = callback_data_for or (lambda child_id, _item: f"id={child_id}")
    rows: list[list[Any]] = []
    row: list[Any] = []

    for child_id, child in children.items():
        if include is not None and not include(str(child_id), child):
            continue
        if child.get("break_before") and row:
            rows.append(row)
            row = []

        row.append(
            build_button(
                child,
                default_callback_data=callback_factory(str(child_id), child),
            )
        )
        if child.get("break_after") or len(row) >= column_count:
            rows.append(row)
            row = []

    if row:
        rows.append(row)
    return _validate_built_rows(rows) if rows else []


def build_view_rows(
    view: Mapping[str, Any],
    actions: Mapping[str, Mapping[str, Any]],
) -> list[list[Any]]:
    """Resolve named action references and build a named view's keyboard."""

    raw_rows = view.get("rows")
    if not isinstance(raw_rows, (list, tuple)):
        raise TypeError("View must define rows as a list")

    rows: list[list[Any]] = []
    for row_number, raw_row in enumerate(raw_rows, start=1):
        if not isinstance(raw_row, (list, tuple)) or not raw_row:
            raise ValueError(f"Button row {row_number} must be a non-empty list")
        row: list[Any] = []
        for cell in raw_row:
            if isinstance(cell, str):
                try:
                    spec = actions[cell]
                except KeyError as error:
                    raise ValueError(f"View references unknown action {cell!r}") from error
            elif isinstance(cell, Mapping):
                spec = cell
            else:
                raise TypeError("View cells must be action ids or button mappings")
            row.append(build_button(spec))
        rows.append(row)
    return _validate_built_rows(rows)
