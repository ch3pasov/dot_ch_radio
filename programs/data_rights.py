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
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from telethon.errors import MessageNotModifiedError

from libs.message_effects import resolve_message_effect, send_with_effect_retry
from libs.telegram_ui import build_view_rows


CALLBACK_PREFIX = "data_rights:"
CALLBACK_HOME = f"{CALLBACK_PREFIX}home"
CALLBACK_AUDIT = f"{CALLBACK_PREFIX}audit"
CALLBACK_TAKEOUT = f"{CALLBACK_PREFIX}takeout"
CALLBACK_DELETE = f"{CALLBACK_PREFIX}delete"
CALLBACK_DELETE_CONFIRM = f"{CALLBACK_PREFIX}delete_confirm"

TAKEOUT_FILENAME = "dot_ch_bot_takeout.zip"
TAKEOUT_TIMEZONE = ZoneInfo("Europe/Berlin")

DATASETS = (
    ("profiles", "Профили пользователей"),
    ("request_history", "История запросов"),
    ("preferences", "Настройки и контекст"),
    ("uploaded_media", "Копии присланных файлов"),
    ("analytics", "Аналитика и трекинг"),
)

_LOGGER = logging.getLogger(__name__)
_ERROR_VIEWS = {
    CALLBACK_AUDIT: "error_audit",
    CALLBACK_TAKEOUT: "error_takeout",
    CALLBACK_DELETE: "error_delete",
    CALLBACK_DELETE_CONFIRM: "error_delete_confirm",
}


def is_data_rights_callback(data: str) -> bool:
    return data.startswith(CALLBACK_PREFIX)


def _view_buttons(ui: Mapping[str, Any], view_name: str):
    return build_view_rows(ui["views"][view_name], ui["actions"])


def _action_effect_id(ui: Mapping[str, Any], action_name: str) -> int | None:
    return resolve_message_effect(ui["actions"][action_name].get("message_effects", ()))


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
    ui: Mapping[str, Any],
    action_name: str,
):
    effect_id = _action_effect_id(ui, action_name)

    async with client.action(chat_id, "document") as action:
        async def send_with_progress(current_effect_id):
            file_obj.seek(0)
            return await client.send_file(
                chat_id,
                file_obj,
                caption=caption,
                force_document=True,
                allow_cache=False,
                reply_to=message.id,
                buttons=_view_buttons(ui, "document"),
                parse_mode="markdown",
                message_effect_id=current_effect_id,
                progress_callback=action.progress,
            )

        return await send_with_effect_retry(send_with_progress, effect_id)


async def _run_audit(client, chat_id: int, message, ui: Mapping[str, Any]):
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
        buttons=_view_buttons(ui, "result"),
    )


async def _run_takeout(client, chat_id: int, message, ui: Mapping[str, Any]):
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
        ui=ui,
        action_name="takeout",
    )
    await _edit(
        message,
        "**✅ Takeout завершён**\n\n"
        "Экспортировано: `0` записей · `0 Б`\n"
        "Архив отправлен следующим сообщением. Внутри — пустой `data.txt`.",
        buttons=_view_buttons(ui, "result"),
    )


async def _show_delete_confirmation(message, ui: Mapping[str, Any]):
    await _edit(
        message,
        "**🗑 Безвозвратное удаление**\n\n"
        "Будут проверены все постоянные хранилища приложения и удалено всё, "
        "что связано с вами — если найдётся хоть что-нибудь.\n\n"
        "Сообщения в этом чате находятся в Telegram и этой операцией не "
        "удаляются. Ими можно управлять средствами Telegram.\n\n"
        "**Действие нельзя отменить. Особенно если нечего отменять.**",
        buttons=_view_buttons(ui, "delete_confirmation"),
    )


async def _run_deletion(client, chat_id: int, message, ui: Mapping[str, Any]):
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
        buttons=_view_buttons(ui, "deletion_result"),
    )

    async def send(current_effect_id):
        return await client.send_message(
            chat_id,
            "✨ **Готово.** Ваш цифровой след в хранилищах бота весит `0 Б`.",
            reply_to=message.id,
            message_effect_id=current_effect_id,
        )

    await send_with_effect_retry(send, _action_effect_id(ui, "delete_confirm"))


async def handle_data_rights_callback(
    event,
    client,
    ui: Mapping[str, Any],
) -> str | None:
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
            await _run_audit(client, event.chat_id, message, ui)
        elif data == CALLBACK_TAKEOUT:
            await event.answer("Готовлю полную выгрузку")
            await _run_takeout(client, event.chat_id, message, ui)
        elif data == CALLBACK_DELETE:
            await event.answer(
                "Удаление касается хранилищ приложения. История чата в Telegram останется на месте.",
                alert=True,
            )
            await _show_delete_confirmation(message, ui)
        elif data == CALLBACK_DELETE_CONFIRM:
            await event.answer("Безвозвратное удаление запущено")
            await _run_deletion(client, event.chat_id, message, ui)
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
            buttons=_view_buttons(ui, _ERROR_VIEWS.get(data, "error_audit")),
        )
    return "handled"
