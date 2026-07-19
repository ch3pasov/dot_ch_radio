"""Stateless helpers for Telegram menu callback payloads."""

from libs.telegram_delivery import DeliveryResult

REFRESH_CALLBACK_PREFIX = "refresh=1="
REFRESH_UNCHANGED_FEEDBACK = "Обновлено (ничего не изменилось)"


def is_refresh_callback(value: str) -> bool:
    return value.startswith(f"{REFRESH_CALLBACK_PREFIX}id=")


def unwrap_refresh_callback(value: str) -> str:
    if is_refresh_callback(value):
        return value[len(REFRESH_CALLBACK_PREFIX):]
    return value


def refresh_feedback_text(changed: bool) -> str | None:
    """Return feedback only when a refresh has no visible result of its own."""

    return None if changed else REFRESH_UNCHANGED_FEEDBACK


async def answer_refresh_callback(event, result) -> None:
    """Finish a refresh callback once with native, result-aware feedback."""

    if isinstance(result, DeliveryResult):
        feedback = refresh_feedback_text(result.changed)
    elif isinstance(result, str) and result:
        feedback = result
    else:
        feedback = refresh_feedback_text(changed=True)
    if feedback is None:
        await event.answer(cache_time=0)
    else:
        await event.answer(feedback, cache_time=0)
