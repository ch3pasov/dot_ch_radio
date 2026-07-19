"""Deliver one fully rendered Telegram page by sending or editing a message."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from telethon.errors import MessageNotModifiedError, ReplyMarkupTooLongError


@dataclass(frozen=True)
class DeliveryResult:
    """The delivered Telegram message and whether its visible state changed."""

    message: Any
    changed: bool


async def deliver_message(
    client,
    message,
    chat_id: int,
    text: str,
    *,
    buttons=None,
    link_preview: bool = True,
    file=None,
    parse_mode: Any = (),
):
    """Send or edit one final page and report whether Telegram changed it."""

    async def deliver(body: str, *, markup, media):
        kwargs = {
            "buttons": markup or None,
            "link_preview": link_preview,
            "file": media,
            "parse_mode": parse_mode,
        }
        if message is None:
            delivered = await client.send_message(chat_id, body, **kwargs)
        else:
            delivered = await message.edit(body, **kwargs)
        return DeliveryResult(delivered, changed=True)

    try:
        return await deliver(text, markup=buttons, media=file)
    except MessageNotModifiedError:
        if message is None:
            raise
        return DeliveryResult(message, changed=False)
    except ReplyMarkupTooLongError:
        fallback = (
            f"{text}\n\n"
            "⚠️ Не смог отрисовать клавиатуру: Telegram отклонил слишком большую разметку."
        )
        try:
            return await deliver(fallback, markup=None, media=None)
        except MessageNotModifiedError:
            if message is None:
                raise
            return DeliveryResult(message, changed=False)
