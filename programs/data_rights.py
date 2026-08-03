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

from libs.i18n import RU, localized, normalize_locale
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
DATASETS_EN = (
    ("profiles", "User profiles"),
    ("request_history", "Request history"),
    ("preferences", "Settings and context"),
    ("uploaded_media", "Copies of uploaded files"),
    ("analytics", "Analytics and tracking"),
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


async def _run_audit(client, chat_id: int, message, ui: Mapping[str, Any], *, locale=RU):
    frames_ru = [
        "**🔎 Аудит хранилищ**\n\n`█░░░░░░░░░ 10%`\nИщу хранилище профилей…",
        "**🔎 Аудит хранилищ**\n\n`███░░░░░░░ 30%`\nПрофили: хранилище не настроено.\nПроверяю историю запросов…",
        "**🔎 Аудит хранилищ**\n\n`█████░░░░░ 50%`\n"
        "История запросов: хранилище не настроено.\nПроверяю настройки и контекст…",
        "**🔎 Аудит хранилищ**\n\n`███████░░░ 70%`\nНастройки: хранилище не настроено.\nИщу копии файлов и аналитику…",
        "**🔎 Аудит хранилищ**\n\n`█████████░ 90%`\nФайлы: 0. Аналитика: 0.\nСверяю итоговый баланс…",
    ]
    frames_en = [
        "**🔎 Storage audit**\n\n`█░░░░░░░░░ 10%`\nLooking for profile storage…",
        "**🔎 Storage audit**\n\n`███░░░░░░░ 30%`\nProfiles: no storage configured.\nChecking request history…",
        "**🔎 Storage audit**\n\n`█████░░░░░ 50%`\n"
        "Request history: no storage configured.\nChecking settings and context…",
        "**🔎 Storage audit**\n\n`███████░░░ 70%`\nSettings: no storage configured.\nLooking for file copies and analytics…",
        "**🔎 Storage audit**\n\n`█████████░ 90%`\nFiles: 0. Analytics: 0.\nBalancing the final total…",
    ]
    frames = frames_ru if normalize_locale(locale) == RU else frames_en
    async with client.action(chat_id, "typing"):
        await _animate(message, frames)

    datasets = DATASETS if normalize_locale(locale) == RU else DATASETS_EN
    lines = "\n".join(f"• {label}: `0`" for _, label in datasets)
    await _edit(
        message,
        localized(
            locale,
            ru=(
                "**✅ Аудит завершён**\n\n"
                "`██████████ 100%`\n\n"
                "{lines}\n\n"
                "**Итого: `0` объектов · `0 Б`**\n\n"
                "У приложения нет базы пользователей, истории запросов, профилей "
                "или пользовательской аналитики. Telegram при этом обрабатывает "
                "сообщения и служебные данные по собственным правилам."
            ),
            en=(
                "**✅ Audit complete**\n\n"
                "`██████████ 100%`\n\n"
                "{lines}\n\n"
                "**Total: `0` objects · `0 B`**\n\n"
                "The application has no user database, request history, profiles or user analytics. "
                "Telegram still processes messages and service data under its own rules."
            ),
            lines=lines,
        ),
        buttons=_view_buttons(ui, "result"),
    )


async def _run_takeout(client, chat_id: int, message, ui: Mapping[str, Any], *, locale=RU):
    frames_ru = [
        "**📦 Takeout: полная выгрузка**\n\n`█░░░░░░░░░ 10%`\nГотовлю экспорт…",
        "**📦 Takeout: полная выгрузка**\n\n`███░░░░░░░ 30%`\nСоздаю data.txt…",
        "**📦 Takeout: полная выгрузка**\n\n`██████░░░░ 60%`\nПроверяю содержимое: 0 Б.",
        "**📦 Takeout: полная выгрузка**\n\n`████████░░ 80%`\nЗаписываю время формирования…",
        "**📦 Takeout: полная выгрузка**\n\n`██████████ 100%`\nУпаковываю data.txt…",
    ]
    frames_en = [
        "**📦 Takeout: complete export**\n\n`█░░░░░░░░░ 10%`\nPreparing the export…",
        "**📦 Takeout: complete export**\n\n`███░░░░░░░ 30%`\nCreating data.txt…",
        "**📦 Takeout: complete export**\n\n`██████░░░░ 60%`\nChecking contents: 0 B.",
        "**📦 Takeout: complete export**\n\n`████████░░ 80%`\nRecording the generation time…",
        "**📦 Takeout: complete export**\n\n`██████████ 100%`\nPacking data.txt…",
    ]
    frames = frames_ru if normalize_locale(locale) == RU else frames_en
    await _animate(message, frames)
    archive = build_takeout_archive()
    await _send_memory_document(
        client,
        chat_id,
        message,
        archive,
        caption=localized(
            locale,
            ru=(
                "**📦 Полная выгрузка готова**\n\n"
                "Записей: `0`\n"
                "Пользовательских данных: `0 Б`\n\n"
                "Архив собран в оперативной памяти и не сохранялся ботом."
            ),
            en=(
                "**📦 Complete export ready**\n\n"
                "Records: `0`\n"
                "User data: `0 B`\n\n"
                "The archive was assembled in memory and was not saved by the bot."
            ),
        ),
        ui=ui,
        action_name="takeout",
    )
    await _edit(
        message,
        localized(
            locale,
            ru=(
                "**✅ Takeout завершён**\n\n"
                "Экспортировано: `0` записей · `0 Б`\n"
                "Архив отправлен следующим сообщением. Внутри — пустой `data.txt`."
            ),
            en=(
                "**✅ Takeout complete**\n\n"
                "Exported: `0` records · `0 B`\n"
                "The archive was sent in the next message. It contains an empty `data.txt`."
            ),
        ),
        buttons=_view_buttons(ui, "result"),
    )


async def _show_delete_confirmation(message, ui: Mapping[str, Any], *, locale=RU):
    await _edit(
        message,
        localized(
            locale,
            ru=(
                "**🗑 Безвозвратное удаление**\n\n"
                "Будут проверены все постоянные хранилища приложения и удалено всё, "
                "что связано с вами — если найдётся хоть что-нибудь.\n\n"
                "Сообщения в этом чате находятся в Telegram и этой операцией не "
                "удаляются. Ими можно управлять средствами Telegram.\n\n"
                "**Действие нельзя отменить. Особенно если нечего отменять.**"
            ),
            en=(
                "**🗑 Permanent deletion**\n\n"
                "All persistent application storage will be checked, and everything associated with you "
                "will be deleted if anything is found.\n\n"
                "Messages in this chat are stored by Telegram and are not deleted by this operation. "
                "Use Telegram's own controls to manage them.\n\n"
                "**This action cannot be undone. Especially if there is nothing to undo.**"
            ),
        ),
        buttons=_view_buttons(ui, "delete_confirmation"),
    )


async def _run_deletion(client, chat_id: int, message, ui: Mapping[str, Any], *, locale=RU):
    frames_ru = [
        "**🗑 Удаление данных**\n\n`█░░░░░░░░░ 10%`\nЗакрываю канал записи… канал отсутствует.",
        "**🗑 Удаление данных**\n\n`███░░░░░░░ 30%`\nУдаляю профиль… таблица не существует.",
        "**🗑 Удаление данных**\n\n`█████░░░░░ 50%`\nОчищаю историю запросов… история не велась.",
        "**🗑 Удаление данных**\n\n`███████░░░ 70%`\nСтираю настройки и файлы… сохранённых копий нет.",
        "**🗑 Удаление данных**\n\n`█████████░ 90%`\nИщу резервные копии… резервных копий нет.",
        "**🗑 Удаление данных**\n\n`██████████ 100%`\nПроверяю, что ноль равен нулю…",
    ]
    frames_en = [
        "**🗑 Data deletion**\n\n`█░░░░░░░░░ 10%`\nClosing the write channel… no channel exists.",
        "**🗑 Data deletion**\n\n`███░░░░░░░ 30%`\nDeleting the profile… no table exists.",
        "**🗑 Data deletion**\n\n`█████░░░░░ 50%`\nClearing request history… no history was kept.",
        "**🗑 Data deletion**\n\n`███████░░░ 70%`\nErasing settings and files… no copies were saved.",
        "**🗑 Data deletion**\n\n`█████████░ 90%`\nLooking for backups… no backups exist.",
        "**🗑 Data deletion**\n\n`██████████ 100%`\nChecking that zero equals zero…",
    ]
    frames = frames_ru if normalize_locale(locale) == RU else frames_en
    async with client.action(chat_id, "typing"):
        await _animate(message, frames, delay=0.55)

    await _edit(
        message,
        localized(
            locale,
            ru=(
                "**✅ Удаление завершено**\n\n"
                "`██████████ 100%`\n\n"
                "Найдено: `0` объектов\n"
                "Удалено: `0` объектов\n"
                "Освобождено: `0 Б`\n"
                "Осталось у бота: `0 Б`\n\n"
                "Ни одна запись не была пропущена — записей не было. Сведения о "
                "самой операции приложение тоже не сохранило."
            ),
            en=(
                "**✅ Deletion complete**\n\n"
                "`██████████ 100%`\n\n"
                "Found: `0` objects\n"
                "Deleted: `0` objects\n"
                "Freed: `0 B`\n"
                "Still stored by the bot: `0 B`\n\n"
                "No records were skipped because there were no records. The application did not save "
                "information about this operation either."
            ),
        ),
        buttons=_view_buttons(ui, "deletion_result"),
    )

    async def send(current_effect_id):
        return await client.send_message(
            chat_id,
            localized(
                locale,
                ru="✨ **Готово.** Ваш цифровой след в хранилищах бота весит `0 Б`.",
                en="✨ **Done.** Your digital footprint in the bot's storage weighs `0 B`.",
            ),
            reply_to=message.id,
            message_effect_id=current_effect_id,
        )

    await send_with_effect_retry(send, _action_effect_id(ui, "delete_confirm"))


async def handle_data_rights_callback(
    event,
    client,
    ui: Mapping[str, Any],
    *,
    locale=RU,
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
            await event.answer(localized(locale, ru="Начинаю аудит", en="Starting audit"))
            await _run_audit(client, event.chat_id, message, ui, locale=locale)
        elif data == CALLBACK_TAKEOUT:
            await event.answer(localized(locale, ru="Готовлю полную выгрузку", en="Preparing complete export"))
            await _run_takeout(client, event.chat_id, message, ui, locale=locale)
        elif data == CALLBACK_DELETE:
            await event.answer(
                localized(
                    locale,
                    ru="Удаление касается хранилищ приложения. История чата в Telegram останется на месте.",
                    en="Deletion covers application storage. Your Telegram chat history will remain in place.",
                ),
                alert=True,
            )
            await _show_delete_confirmation(message, ui, locale=locale)
        elif data == CALLBACK_DELETE_CONFIRM:
            await event.answer(localized(
                locale,
                ru="Безвозвратное удаление запущено",
                en="Permanent deletion started",
            ))
            await _run_deletion(client, event.chat_id, message, ui, locale=locale)
        else:
            await event.answer(localized(
                locale,
                ru="Неизвестная операция центра данных",
                en="Unknown data-centre operation",
            ), alert=True)
    except Exception as error:
        # Keep operational logs useful without persisting the callback sender,
        # chat, payload or exception text (which can occasionally contain IDs).
        _LOGGER.error("data-rights operation failed: %s", type(error).__name__)
        await _edit(
            message,
            localized(
                locale,
                ru=(
                    "**⚠️ Операция прервана**\n\n"
                    "Telegram не принял один из шагов. Бот ничего не записал на диск "
                    "и не создал незавершённую заявку — можно безопасно повторить."
                ),
                en=(
                    "**⚠️ Operation interrupted**\n\n"
                    "Telegram rejected one of the steps. The bot wrote nothing to disk and created no "
                    "unfinished request, so it is safe to try again."
                ),
            ),
            buttons=_view_buttons(ui, _ERROR_VIEWS.get(data, "error_audit")),
        )
    return "handled"
