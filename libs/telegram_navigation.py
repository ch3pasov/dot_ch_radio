"""Stateless helpers for Telegram menu callback payloads."""

from libs.telegram_delivery import DeliveryResult
from libs.i18n import RU, localized

REFRESH_CALLBACK_PREFIX = "refresh=1="
REFRESH_UNCHANGED_FEEDBACK = "Обновлено (ничего не изменилось)"


def is_refresh_callback(value: str) -> bool:
    return value.startswith(f"{REFRESH_CALLBACK_PREFIX}id=")


def unwrap_refresh_callback(value: str) -> str:
    if is_refresh_callback(value):
        return value[len(REFRESH_CALLBACK_PREFIX):]
    return value


def refresh_feedback_text(changed: bool, *, locale=RU) -> str | None:
    """Return feedback only when a refresh has no visible result of its own."""

    return None if changed else localized(
        locale,
        ru=REFRESH_UNCHANGED_FEEDBACK,
        en="Refreshed (nothing changed)",
    )


async def answer_refresh_callback(event, result, *, locale=RU) -> None:
    """Finish a refresh callback once with native, result-aware feedback."""

    if isinstance(result, DeliveryResult):
        feedback = refresh_feedback_text(result.changed, locale=locale)
    elif isinstance(result, str) and result:
        feedback = result
    else:
        feedback = refresh_feedback_text(changed=True, locale=locale)
    if feedback is None:
        await event.answer(cache_time=0)
    else:
        await event.answer(feedback, cache_time=0)
