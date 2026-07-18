"""Declarative schema helpers for the bot content tree.

The content tree stays plain data.  This module normalizes the compact DSL to
the dict shape consumed by the route index and validates Telegram UI limits
before a handler tries to render the tree.
"""

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Iterable, Mapping


BUTTON_STYLES = frozenset({"primary", "danger", "success"})
NAVIGATION_ACTIONS = frozenset({"back", "share", "refresh"})
MAX_CALLBACK_DATA_BYTES = 64
MAX_BUTTONS_PER_ROW = 8
MAX_BUTTONS_PER_MARKUP = 100

_ACTION_TARGET_FIELDS = (
    "url",
    "copy_text",
    "web_app_url",
    "simple_web_app_url",
    "callback_data",
    "user_id",
    "switch_inline_query",
    "switch_inline_query_current_chat",
)


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
    if not isinstance(style, str):
        raise TypeError("button_style must be a string or None")
    normalized = style.lower()
    if normalized not in BUTTON_STYLES:
        raise ValueError(f"Unknown button_style {style!r}; expected one of {sorted(BUTTON_STYLES)}")
    return normalized


def validate_button_icon(icon: int | str | None) -> int | None:
    """Return a positive Telegram custom-emoji document id."""

    if icon is None:
        return None
    if isinstance(icon, bool):
        raise TypeError("button_icon must be a positive integer document id")
    if isinstance(icon, str):
        if not icon.isdecimal():
            raise ValueError("button_icon must be a positive integer document id")
        icon = int(icon)
    if not isinstance(icon, int):
        raise TypeError("button_icon must be a positive integer document id")
    if icon <= 0:
        raise ValueError("button_icon must be a positive integer document id")
    return icon


def validate_callback_data(data: str | bytes) -> str | bytes:
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        raise TypeError("callback_data must be str or bytes")
    if len(payload) > MAX_CALLBACK_DATA_BYTES:
        raise ValueError(f"callback_data exceeds Telegram's {MAX_CALLBACK_DATA_BYTES}-byte limit")
    return data


def validate_children_columns(columns: int) -> int:
    if isinstance(columns, bool) or not isinstance(columns, int):
        raise TypeError("children_columns must be an integer")
    if not 1 <= columns <= MAX_BUTTONS_PER_ROW:
        raise ValueError(f"children_columns must be between 1 and {MAX_BUTTONS_PER_ROW}")
    return columns


def validate_message_effects(effects: list[str]) -> list[str]:
    if not isinstance(effects, list):
        raise TypeError("message_effects must be a list of non-empty strings")
    if not effects:
        raise ValueError("message_effects must not be empty")
    if any(not isinstance(effect, str) or not effect.strip() for effect in effects):
        raise ValueError("message_effects must contain only non-empty strings")
    return [effect.strip() for effect in effects]


def normalize_tree(tree: Mapping[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(dict(tree))
    _normalize_node(normalized, is_root=True)
    return normalized


def _move_alias(item: dict[str, Any], alias: str, canonical: str) -> None:
    if alias not in item:
        return
    alias_value = item.pop(alias)
    if canonical in item:
        canonical_value = item[canonical]
        if canonical == "button_style":
            equivalent = validate_button_style(canonical_value) == validate_button_style(alias_value)
        elif canonical == "button_icon":
            equivalent = validate_button_icon(canonical_value) == validate_button_icon(alias_value)
        else:
            equivalent = canonical_value == alias_value
        if not equivalent:
            raise ValueError(f"Conflicting {canonical!r} and legacy alias {alias!r}")
    item.setdefault(canonical, alias_value)


def _normalize_button_fields(
    item: dict[str, Any],
    *,
    allow_message_effects: bool,
    require_action: bool = False,
    require_label: bool = False,
) -> None:
    _move_alias(item, "button_color", "button_style")
    _move_alias(item, "custom_emoji_id", "button_icon")

    if "button_style" in item:
        item["button_style"] = validate_button_style(item["button_style"])
    if "button_icon" in item:
        item["button_icon"] = validate_button_icon(item["button_icon"])
    if "callback_data" in item:
        item["callback_data"] = validate_callback_data(item["callback_data"])

    for field in ("break_before", "break_after"):
        if field in item and not isinstance(item[field], bool):
            raise TypeError(f"{field} must be a boolean")

    if "same_peer" in item and not isinstance(item["same_peer"], bool):
        raise TypeError("same_peer must be a boolean")

    if "message_effects" in item:
        if not allow_message_effects:
            raise ValueError("message_effects are only allowed on entries in actions")
        item["message_effects"] = validate_message_effects(item["message_effects"])

    targets = [field for field in _ACTION_TARGET_FIELDS if field in item]
    if len(targets) > 1:
        raise ValueError(f"Button defines multiple actions: {', '.join(targets)}")
    if require_action and not targets:
        raise ValueError("Action button must define a Telegram action target")
    if require_label and not any(item.get(key) for key in ("button_text", "text", "name")):
        raise ValueError("Button must define name, text, or button_text")

    if item.get("button_type") == "user_profile" and "user_id" not in item:
        raise ValueError("user_profile button requires user_id")


def normalize_button_spec(
    spec: Mapping[str, Any],
    *,
    allow_message_effects: bool = False,
    require_action: bool = False,
    require_label: bool = False,
) -> dict[str, Any]:
    """Normalize one standalone button spec without mutating the input."""

    if not isinstance(spec, Mapping):
        raise TypeError("Button spec must be a mapping")
    normalized = deepcopy(dict(spec))
    _normalize_button_fields(
        normalized,
        allow_message_effects=allow_message_effects,
        require_action=require_action,
        require_label=require_label,
    )
    return normalized


def _normalize_node(item: dict[str, Any], *, is_root: bool = False) -> None:
    _normalize_button_fields(item, allow_message_effects=False)

    if "children_columns" in item:
        item["children_columns"] = validate_children_columns(item["children_columns"])
    if "children_button_style" in item:
        item["children_button_style"] = validate_button_style(item["children_button_style"])

    actions = _normalize_actions(item.get("actions", {}))
    if "actions" in item:
        item["actions"] = actions
    if "views" in item:
        item["views"] = _normalize_views(item["views"], actions)

    if "navigation_ui" in item:
        if not is_root:
            raise ValueError("navigation_ui is only allowed on the root node")
        item["navigation_ui"] = _normalize_navigation_ui(item["navigation_ui"])

    if "children" in item:
        item["children"] = normalize_children(
            item["children"],
            default_button_style=item.get("children_button_style"),
        )


def normalize_children(
    children: Any,
    *,
    default_button_style: str | None = None,
) -> OrderedDict[str, dict[str, Any]]:
    default_style = validate_button_style(default_button_style)
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
        if not isinstance(raw_child, Mapping):
            raise TypeError(f"Child {key!r} must be a mapping")
        child = deepcopy(dict(raw_child))
        child.pop("id", None)
        if default_style is not None and "button_style" not in child and "button_color" not in child:
            child["button_style"] = default_style
        _normalize_node(child)
        normalized[str(key)] = child
    return normalized


def _normalize_actions(actions: Any) -> OrderedDict[str, dict[str, Any]]:
    if not isinstance(actions, Mapping):
        raise TypeError("actions must be a mapping of action ids to button specs")
    if not actions:
        return OrderedDict()

    normalized: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for action_id, raw_action in actions.items():
        if not isinstance(raw_action, Mapping):
            raise TypeError(f"Action {action_id!r} must be a mapping")
        action = deepcopy(dict(raw_action))
        _normalize_button_fields(
            action,
            allow_message_effects=True,
            require_action=True,
            require_label=True,
        )
        normalized[str(action_id)] = action
    return normalized


def _normalize_views(views: Any, actions: Mapping[str, Mapping[str, Any]]) -> OrderedDict[str, dict[str, Any]]:
    if not isinstance(views, Mapping):
        raise TypeError("views must be a mapping of view ids to {rows: ...}")

    normalized: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for view_id, raw_view in views.items():
        if not isinstance(raw_view, Mapping):
            raise TypeError(f"View {view_id!r} must be a mapping")
        view = deepcopy(dict(raw_view))
        if "rows" not in view:
            raise ValueError(f"View {view_id!r} must define rows")
        view["rows"] = _normalize_view_rows(view["rows"], actions, view_id=str(view_id))
        normalized[str(view_id)] = view
    return normalized


def _normalize_view_rows(rows: Any, actions: Mapping[str, Mapping[str, Any]], *, view_id: str) -> list[list[Any]]:
    if not isinstance(rows, (list, tuple)):
        raise TypeError(f"View {view_id!r} rows must be a list")
    if not rows:
        raise ValueError(f"View {view_id!r} rows must not be empty")

    normalized: list[list[Any]] = []
    button_count = 0
    for row_number, raw_row in enumerate(rows, start=1):
        if not isinstance(raw_row, (list, tuple)) or not raw_row:
            raise ValueError(f"View {view_id!r} row {row_number} must be a non-empty list")
        if len(raw_row) > MAX_BUTTONS_PER_ROW:
            raise ValueError(
                f"View {view_id!r} row {row_number} exceeds Telegram's "
                f"{MAX_BUTTONS_PER_ROW}-button limit"
            )
        row: list[Any] = []
        for cell in raw_row:
            if isinstance(cell, str):
                if cell not in actions:
                    raise ValueError(f"View {view_id!r} references unknown action {cell!r}")
                row.append(cell)
            elif isinstance(cell, Mapping):
                inline_spec = deepcopy(dict(cell))
                _normalize_button_fields(
                    inline_spec,
                    allow_message_effects=False,
                    require_action=True,
                    require_label=True,
                )
                row.append(inline_spec)
            else:
                raise TypeError(f"View {view_id!r} cells must be action ids or button mappings")
        button_count += len(row)
        row and normalized.append(row)

    if button_count > MAX_BUTTONS_PER_MARKUP:
        raise ValueError(f"View {view_id!r} exceeds Telegram's {MAX_BUTTONS_PER_MARKUP}-button limit")
    return normalized


def _normalize_navigation_ui(navigation_ui: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(navigation_ui, Mapping):
        raise TypeError("navigation_ui must be a mapping")
    unknown = set(navigation_ui) - NAVIGATION_ACTIONS
    if unknown:
        raise ValueError(f"Unknown navigation_ui entries: {', '.join(sorted(unknown))}")
    missing = NAVIGATION_ACTIONS - set(navigation_ui)
    if missing:
        raise ValueError(f"Missing navigation_ui entries: {', '.join(sorted(missing))}")

    normalized: dict[str, dict[str, Any]] = {}
    for action_name, raw_spec in navigation_ui.items():
        if not isinstance(raw_spec, Mapping):
            raise TypeError(f"navigation_ui.{action_name} must be a button mapping")
        spec = deepcopy(dict(raw_spec))
        _normalize_button_fields(
            spec,
            allow_message_effects=False,
            require_label=True,
        )
        normalized[str(action_name)] = spec
    return normalized
