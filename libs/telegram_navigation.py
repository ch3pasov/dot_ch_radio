"""Stateless helpers for Telegram menu callback payloads."""

from libs.telegram_delivery import DeliveryResult

REFRESH_CALLBACK_PREFIX = "refresh=1="
REFRESH_CHANGED_FEEDBACK = "Обновлено"
REFRESH_UNCHANGED_FEEDBACK = "Уже актуально"


def is_refresh_callback(value: str) -> bool:
    return value.startswith(f"{REFRESH_CALLBACK_PREFIX}id=")


def unwrap_refresh_callback(value: str) -> str:
    if is_refresh_callback(value):
        return value[len(REFRESH_CALLBACK_PREFIX):]
    return value


def refresh_feedback_text(changed: bool) -> str:
    """Return concise native CallbackQuery feedback for a completed refresh."""

    return REFRESH_CHANGED_FEEDBACK if changed else REFRESH_UNCHANGED_FEEDBACK


async def answer_refresh_callback(event, result) -> None:
    """Finish a refresh callback once with native, result-aware feedback."""

    if isinstance(result, DeliveryResult):
        feedback = refresh_feedback_text(result.changed)
    elif isinstance(result, str) and result:
        feedback = result
    else:
        feedback = refresh_feedback_text(changed=True)
    await event.answer(feedback, cache_time=0)
