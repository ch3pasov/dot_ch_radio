"""Stateless locale selection for Telegram events."""

from __future__ import annotations

from typing import Any


RU = "ru"
EN = "en"
SUPPORTED_LOCALES = (RU, EN)
FALLBACK_LOCALE = EN


def normalize_locale(language_code: str | None) -> str:
    """Map Telegram's language code to one of the bot's supported locales."""

    if not isinstance(language_code, str):
        return FALLBACK_LOCALE
    primary_language = language_code.strip().lower().replace("_", "-").split("-", 1)[0]
    return RU if primary_language == RU else FALLBACK_LOCALE


def locale_from_sender(sender: Any) -> str:
    return normalize_locale(getattr(sender, "lang_code", None))


async def locale_from_event(event: Any) -> str:
    """Read a locale from this event without storing a per-user preference."""

    try:
        sender = await event.get_sender()
    except (AttributeError, OSError, RuntimeError):
        return FALLBACK_LOCALE
    return locale_from_sender(sender)


def localized(locale: str, *, ru: str, en: str, **values: Any) -> str:
    """Choose and optionally format a short localized string."""

    template = ru if normalize_locale(locale) == RU else en
    return template.format(**values) if values else template
