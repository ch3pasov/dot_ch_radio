"""Stateless helpers for Telegram menu callback payloads."""

REFRESH_CALLBACK_PREFIX = "refresh=1="


def is_refresh_callback(value: str) -> bool:
    return value.startswith(f"{REFRESH_CALLBACK_PREFIX}id=")


def unwrap_refresh_callback(value: str) -> str:
    if is_refresh_callback(value):
        return value[len(REFRESH_CALLBACK_PREFIX):]
    return value
