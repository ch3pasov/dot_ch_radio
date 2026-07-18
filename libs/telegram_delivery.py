"""Deliver one fully rendered Telegram page by sending or editing a message."""

from __future__ import annotations

from typing import Any

from telethon.errors import MessageNotModifiedError, ReplyMarkupTooLongError


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
    """Send a new final page or edit an existing menu message in one step."""

    async def deliver(body: str, *, markup, media):
        kwargs = {
            "buttons": markup or None,
            "link_preview": link_preview,
            "file": media,
            "parse_mode": parse_mode,
        }
        if message is None:
            return await client.send_message(chat_id, body, **kwargs)
        return await message.edit(body, **kwargs)

    try:
        return await deliver(text, markup=buttons, media=file)
    except MessageNotModifiedError:
        if message is None:
            raise
        return message
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
            return message
