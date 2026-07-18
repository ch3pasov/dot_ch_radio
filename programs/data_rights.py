"""Stateless takeout and deletion performance for the bot's data centre.

The bot has no application-side user store.  Every artifact in this module is
built in memory, contains no request/user identifiers and is never written to
the bot's filesystem.
"""

from __future__ import annotations

import asyncio
import io
import logging
import zipfile
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from telethon import Button
from telethon.errors import MessageNotModifiedError, RPCError
from telethon.tl.functions.messages import GetAvailableEffectsRequest
from telethon.tl.types import KeyboardButtonCopy, KeyboardButtonStyle


CALLBACK_PREFIX = "data_rights:"
CALLBACK_HOME = f"{CALLBACK_PREFIX}home"
CALLBACK_AUDIT = f"{CALLBACK_PREFIX}audit"
CALLBACK_TAKEOUT = f"{CALLBACK_PREFIX}takeout"
CALLBACK_DELETE = f"{CALLBACK_PREFIX}delete"
CALLBACK_DELETE_CONFIRM = f"{CALLBACK_PREFIX}delete_confirm"
CALLBACK_RECEIPT = f"{CALLBACK_PREFIX}receipt"

TAKEOUT_FILENAME = "dot_ch_bot_takeout.zip"
RECEIPT_FILENAME = "dot_ch_bot_nothing_deleted.txt"
ZERO_SUMMARY = "@dot_ch_bot · найдено 0 · удалено 0 · хранится 0 Б"
TAKEOUT_TIMEZONE = ZoneInfo("Europe/Berlin")

DATASETS = (
    ("profiles", "Профили пользователей"),
    ("request_history", "История запросов"),
    ("preferences", "Настройки и контекст"),
    ("uploaded_media", "Копии присланных файлов"),
    ("analytics", "Аналитика и трекинг"),
)

_MESSAGE_EFFECT_IDS: dict[str, int] = {}
_LOGGER = logging.getLogger(__name__)


def is_data_rights_callback(data: str) -> bool:
    return data.startswith(CALLBACK_PREFIX)


def _callback_button(text: str, data: str, *, style: str | None = None):
    payload = data.encode("ascii")
    if len(payload) > 64:
        raise ValueError("Telegram callback payload exceeds 64 bytes")
    return Button.inline(text, data=payload, style=style)


def _copy_summary_button():
    return KeyboardButtonCopy(
        "📋 Скопировать итог",
        ZERO_SUMMARY,
        style=KeyboardButtonStyle(bg_success=True),
    )


def _home_button():
    return _callback_button("↩️ В центр данных", CALLBACK_HOME)


def _result_buttons():
    return [
        [_copy_summary_button()],
        [
            _callback_button("📦 Takeout", CALLBACK_TAKEOUT, style="primary"),
            _callback_button("🗑 Удалить", CALLBACK_DELETE, style="danger"),
        ],
        [_home_button()],
    ]


def _delete_confirmation_buttons():
    return [
        [_callback_button("🗑 Удалить безвозвратно", CALLBACK_DELETE_CONFIRM, style="danger")],
        [_home_button()],
    ]


def _deletion_result_buttons():
    return [
        [_copy_summary_button()],
        [_callback_button("🧾 Получить акт", CALLBACK_RECEIPT, style="primary")],
        [_home_button()],
    ]


def _error_buttons(retry_callback: str):
    style = "danger" if retry_callback == CALLBACK_DELETE_CONFIRM else "primary"
    return [
        [_callback_button("↻ Повторить", retry_callback, style=style)],
        [_home_button()],
    ]


def _takeout_zip_time(generated_at: datetime) -> tuple[int, int, int, int, int, int]:
    """Return the Berlin wall-clock time representable by a ZIP entry."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    local_time = generated_at.astimezone(TAKEOUT_TIMEZONE)
    return (
        local_time.year,
        local_time.month,
        local_time.day,
        local_time.hour,
        local_time.minute,
        local_time.second - local_time.second % 2,
    )


def _zip_add_empty_file(
    archive: zipfile.ZipFile,
    name: str,
    *,
    generated_at: datetime,
):
    info = zipfile.ZipInfo(name, date_time=_takeout_zip_time(generated_at))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    archive.writestr(info, b"")


def build_takeout_archive(*, generated_at: datetime | None = None) -> io.BytesIO:
    generated_at = generated_at or datetime.now(tz=TAKEOUT_TIMEZONE)
    output = io.BytesIO()
    output.name = TAKEOUT_FILENAME
    with zipfile.ZipFile(output, "w") as archive:
        _zip_add_empty_file(
            archive,
            "data.txt",
            generated_at=generated_at,
        )
    output.seek(0)
    return output


def build_deletion_receipt() -> io.BytesIO:
    text = (
        "АКТ ОБ ОТСУТСТВИИ ДАННЫХ № 0\n"
        "================================\n\n"
        "Область проверки: постоянные хранилища приложения @dot_ch_bot\n"
        "Найдено объектов: 0\n"
        "Удалено объектов: 0\n"
        "Освобождено: 0 байт\n"
        "Осталось в хранилищах бота: 0 байт\n"
        "Статус: NOTHING_TO_DELETE\n\n"
        "Приложение не сохранило идентификатор запроса, имя пользователя,\n"
        "Telegram ID, время операции или копию этого акта. Документ был\n"
        "сформирован в оперативной памяти.\n\n"
        "Это перформативный технический акт, а не юридическая справка.\n"
        "История чата в Telegram находится вне хранилищ приложения.\n"
    )
    output = io.BytesIO(text.encode("utf-8"))
    output.name = RECEIPT_FILENAME
    output.seek(0)
    return output


async def load_message_effects(user_client) -> int:
    """Load Telegram's non-premium one-to-one effects once at startup.

    Telegram only allows user accounts to query the effect catalogue, so the
    already-required DJ client supplies the IDs. Failure is harmless: the
    entire flow works without an animation.
    """

    try:
        result = await user_client(GetAvailableEffectsRequest(hash=0))
    except Exception:
        _MESSAGE_EFFECT_IDS.clear()
        return 0

    loaded = {
        effect.emoticon: effect.id
        for effect in getattr(result, "effects", ())
        if not getattr(effect, "premium_required", False)
    }
    _MESSAGE_EFFECT_IDS.clear()
    _MESSAGE_EFFECT_IDS.update(loaded)
    return len(loaded)


def _message_effect_id(preferred_emoticons: Iterable[str]) -> int | None:
    for emoticon in preferred_emoticons:
        effect_id = _MESSAGE_EFFECT_IDS.get(emoticon)
        if effect_id is not None:
            return effect_id
    return next(iter(_MESSAGE_EFFECT_IDS.values()), None)


async def _edit(message, text: str, *, buttons=None):
    try:
        return await message.edit(
            text,
            buttons=buttons or None,
            link_preview=False,
            parse_mode="markdown",
        )
    except MessageNotModifiedError:
        return message


async def _animate(message, frames, *, delay: float = 0.48):
    for frame in frames:
        await _edit(message, frame)
        await asyncio.sleep(delay)


async def _send_memory_document(
    client,
    chat_id: int,
    message,
    file_obj: io.BytesIO,
    *,
    caption: str,
    effect_emoticons: Iterable[str],
):
    effect_id = _message_effect_id(effect_emoticons)
    kwargs = {
        "caption": caption,
        "force_document": True,
        "allow_cache": False,
        "reply_to": message.id,
        "buttons": [[_copy_summary_button()]],
        "parse_mode": "markdown",
        "message_effect_id": effect_id,
    }
    async with client.action(chat_id, "document") as action:
        kwargs["progress_callback"] = action.progress
        try:
            file_obj.seek(0)
            return await client.send_file(chat_id, file_obj, **kwargs)
        except RPCError as error:
            # A catalogue can change between startup and send. Retry only the
            # effect-specific failure, never arbitrary network/flood errors.
            if effect_id is None or "EFFECT" not in str(error).upper():
                raise
            kwargs["message_effect_id"] = None
            file_obj.seek(0)
            return await client.send_file(chat_id, file_obj, **kwargs)


async def _run_audit(client, chat_id: int, message):
    frames = [
        "**🔎 Аудит хранилищ**\n\n`█░░░░░░░░░ 10%`\nИщу хранилище профилей…",
        "**🔎 Аудит хранилищ**\n\n`███░░░░░░░ 30%`\nПрофили: хранилище не настроено.\nПроверяю историю запросов…",
        "**🔎 Аудит хранилищ**\n\n`█████░░░░░ 50%`\n"
        "История запросов: хранилище не настроено.\nПроверяю настройки и контекст…",
        "**🔎 Аудит хранилищ**\n\n`███████░░░ 70%`\nНастройки: хранилище не настроено.\nИщу копии файлов и аналитику…",
        "**🔎 Аудит хранилищ**\n\n`█████████░ 90%`\nФайлы: 0. Аналитика: 0.\nСверяю итоговый баланс…",
    ]
    async with client.action(chat_id, "typing"):
        await _animate(message, frames)

    lines = "\n".join(f"• {label}: `0`" for _, label in DATASETS)
    await _edit(
        message,
        "**✅ Аудит завершён**\n\n"
        "`██████████ 100%`\n\n"
        f"{lines}\n\n"
        "**Итого: `0` объектов · `0 Б`**\n\n"
        "У приложения нет базы пользователей, истории запросов, профилей "
        "или пользовательской аналитики. Telegram при этом обрабатывает "
        "сообщения и служебные данные по собственным правилам.",
        buttons=_result_buttons(),
    )


async def _run_takeout(client, chat_id: int, message):
    frames = [
        "**📦 Takeout: полная выгрузка**\n\n`█░░░░░░░░░ 10%`\nГотовлю экспорт…",
        "**📦 Takeout: полная выгрузка**\n\n`███░░░░░░░ 30%`\nСоздаю data.txt…",
        "**📦 Takeout: полная выгрузка**\n\n`██████░░░░ 60%`\nПроверяю содержимое: 0 Б.",
        "**📦 Takeout: полная выгрузка**\n\n`████████░░ 80%`\nЗаписываю время формирования…",
        "**📦 Takeout: полная выгрузка**\n\n`██████████ 100%`\nУпаковываю data.txt…",
    ]
    await _animate(message, frames)
    archive = build_takeout_archive()
    await _send_memory_document(
        client,
        chat_id,
        message,
        archive,
        caption=(
            "**📦 Полная выгрузка готова**\n\n"
            "Записей: `0`\n"
            "Пользовательских данных: `0 Б`\n\n"
            "Архив собран в оперативной памяти и не сохранялся ботом."
        ),
        effect_emoticons=("🎉", "👍"),
    )
    await _edit(
        message,
        "**✅ Takeout завершён**\n\n"
        "Экспортировано: `0` записей · `0 Б`\n"
        "Архив отправлен следующим сообщением. Внутри — пустой `data.txt`.",
        buttons=_result_buttons(),
    )


async def _show_delete_confirmation(message):
    await _edit(
        message,
        "**🗑 Безвозвратное удаление**\n\n"
        "Будут проверены все постоянные хранилища приложения и удалено всё, "
        "что связано с вами — если найдётся хоть что-нибудь.\n\n"
        "Сообщения в этом чате находятся в Telegram и этой операцией не "
        "удаляются. Ими можно управлять средствами Telegram.\n\n"
        "**Действие нельзя отменить. Особенно если нечего отменять.**",
        buttons=_delete_confirmation_buttons(),
    )


async def _run_deletion(client, chat_id: int, message):
    frames = [
        "**🗑 Удаление данных**\n\n`█░░░░░░░░░ 10%`\nЗакрываю канал записи… канал отсутствует.",
        "**🗑 Удаление данных**\n\n`███░░░░░░░ 30%`\nУдаляю профиль… таблица не существует.",
        "**🗑 Удаление данных**\n\n`█████░░░░░ 50%`\nОчищаю историю запросов… история не велась.",
        "**🗑 Удаление данных**\n\n`███████░░░ 70%`\nСтираю настройки и файлы… сохранённых копий нет.",
        "**🗑 Удаление данных**\n\n`█████████░ 90%`\nИщу резервные копии… резервных копий нет.",
        "**🗑 Удаление данных**\n\n`██████████ 100%`\nПроверяю, что ноль равен нулю…",
    ]
    async with client.action(chat_id, "typing"):
        await _animate(message, frames, delay=0.55)

    await _edit(
        message,
        "**✅ Удаление завершено**\n\n"
        "`██████████ 100%`\n\n"
        "Найдено: `0` объектов\n"
        "Удалено: `0` объектов\n"
        "Освобождено: `0 Б`\n"
        "Осталось у бота: `0 Б`\n\n"
        "Ни одна запись не была пропущена — записей не было. Сведения о "
        "самой операции приложение тоже не сохранило.",
        buttons=_deletion_result_buttons(),
    )

    effect_id = _message_effect_id(("🎉", "🔥", "👍"))
    kwargs = {"reply_to": message.id, "message_effect_id": effect_id}
    try:
        await client.send_message(
            chat_id,
            "✨ **Готово.** Ваш цифровой след в хранилищах бота весит `0 Б`.",
            **kwargs,
        )
    except RPCError as error:
        if effect_id is None or "EFFECT" not in str(error).upper():
            raise
        kwargs["message_effect_id"] = None
        await client.send_message(
            chat_id,
            "✨ **Готово.** Ваш цифровой след в хранилищах бота весит `0 Б`.",
            **kwargs,
        )


async def _send_receipt(client, chat_id: int, message):
    receipt = build_deletion_receipt()
    await _send_memory_document(
        client,
        chat_id,
        message,
        receipt,
        caption=(
            "**🧾 Акт № 0**\n\n"
            "Официально подтверждает успешное удаление всех нуля объектов. "
            "Копия акта у бота не остаётся."
        ),
        effect_emoticons=("👍", "🎉"),
    )


async def handle_data_rights_callback(event, client) -> str | None:
    """Handle one stateless callback; return ``"home"`` for menu navigation."""

    data = event.data.decode("ascii", errors="strict")
    if not is_data_rights_callback(data):
        return None

    if data == CALLBACK_HOME:
        await event.answer()
        return "home"

    message = await event.get_message()
    try:
        if data == CALLBACK_AUDIT:
            await event.answer("Начинаю аудит")
            await _run_audit(client, event.chat_id, message)
        elif data == CALLBACK_TAKEOUT:
            await event.answer("Готовлю полную выгрузку")
            await _run_takeout(client, event.chat_id, message)
        elif data == CALLBACK_DELETE:
            await event.answer(
                "Удаление касается хранилищ приложения. История чата в Telegram останется на месте.",
                alert=True,
            )
            await _show_delete_confirmation(message)
        elif data == CALLBACK_DELETE_CONFIRM:
            await event.answer("Безвозвратное удаление запущено")
            await _run_deletion(client, event.chat_id, message)
        elif data == CALLBACK_RECEIPT:
            await event.answer("Формирую акт в оперативной памяти")
            await _send_receipt(client, event.chat_id, message)
        else:
            await event.answer("Неизвестная операция центра данных", alert=True)
    except Exception as error:
        # Keep operational logs useful without persisting the callback sender,
        # chat, payload or exception text (which can occasionally contain IDs).
        _LOGGER.error("data-rights operation failed: %s", type(error).__name__)
        await _edit(
            message,
            "**⚠️ Операция прервана**\n\n"
            "Telegram не принял один из шагов. Бот ничего не записал на диск "
            "и не создал незавершённую заявку — можно безопасно повторить.",
            buttons=_error_buttons(data),
        )
    return "handled"
