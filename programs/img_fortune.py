"""Date-based YouTube divination without user or navigation state."""

import calendar
import html
import re
from datetime import date

from telethon import Button
from telethon.errors import MessageNotModifiedError

from libs.i18n import RU, localized, normalize_locale
from libs.img_fortune_catalog import CODE_PATTERN, fortune_video_entry, fortune_video_url


CALLBACK_PREFIX = "img_fortune:"
_DATE_PATTERN = re.compile(r"([0-9]{1,2})\.([0-9]{1,2})(?:\.([0-9]{4}))?")
_MONTHS = {
    RU: (
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ),
    "en": (
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    ),
}


def parse_fortune_date(value: str) -> date:
    """Accept DD.MM or DD.MM.YYYY; a missing year permits February 29."""
    match = _DATE_PATTERN.fullmatch(value.strip())
    if match is None:
        raise ValueError("Expected DD.MM or DD.MM.YYYY")
    day, month, year = match.groups()
    return date(int(year) if year else 2000, int(month), int(day))


def fortune_argument(text: str, *, bot_username: str, is_private: bool) -> str | None:
    """Match explicit commands, plus standalone dates in private chats only."""
    username = re.escape(bot_username)
    command = re.fullmatch(
        rf"(?:@{username}\s+)?/fortune(?:@{username})?(?:\s+([\s\S]*))?",
        text.strip(),
        flags=re.IGNORECASE,
    )
    if command:
        return (command.group(1) or "").strip()
    if is_private and _DATE_PATTERN.fullmatch(text.strip()):
        return text.strip()
    return None


def fortune_code(value: str | date) -> str:
    if isinstance(value, date):
        return f"{value.day:02d}{value.month:02d}"
    value = value.strip()
    if CODE_PATTERN.fullmatch(value):
        return value
    return fortune_code(parse_fortune_date(value))


def fortune_query(value: str | date) -> str:
    return f"IMG_{fortune_code(value)}"


def _back_button(locale):
    return Button.inline(
        localized(locale, ru="⬅️ Назад", en="⬅️ Back"),
        data="img_fortune",
    )


def _choose_date_button(locale):
    return Button.inline(
        localized(locale, ru="Выбрать дату", en="Choose a date"),
        data=f"{CALLBACK_PREFIX}months",
    )


def fortune_view(value: str | date, *, locale=RU):
    code = fortune_code(value)
    video = fortune_video_entry(code)
    video_url = fortune_video_url(code)
    label = f"{value.day:02d}.{value.month:02d} → " if isinstance(value, date) else ""
    exception_note = ""
    if video.get("match_type") == "descriptive_title":
        exception_note = localized(
            locale,
            ru="\n\nНазвание найденного ролика: <code>{title}</code>",
            en="\n\nFound video title: <code>{title}</code>",
            title=html.escape(video["title"], quote=False),
        )
    text = localized(
        locale,
        ru=(
            "🔮 <b>Гадание по дате</b>\n\n"
            "{label}<code>{query}</code>\n\n"
            "Вот твоё предсказание. Толкование самостоятельное.\n\n"
            "{video_url}{exception_note}"
        ),
        en=(
            "🔮 <b>Date divination</b>\n\n"
            "{label}<code>{query}</code>\n\n"
            "Here's your prediction. Interpretation is up to you.\n\n"
            "{video_url}{exception_note}"
        ),
        label=label,
        query=f"IMG_{code}",
        video_url=video_url,
        exception_note=exception_note,
    )
    buttons = [
        [Button.url(
            localized(locale, ru="Открыть YouTube", en="Open YouTube"),
            video_url,
        )],
        [_choose_date_button(locale), _back_button(locale)],
    ]
    return text, buttons


def month_picker_view(*, locale=RU):
    text = localized(
        locale,
        ru="🔮 <b>Гадание по дате</b>\n\nВыбери месяц. Затем — день.",
        en="🔮 <b>Date divination</b>\n\nChoose a month, then a day.",
    )
    months = [
        Button.inline(name, data=f"{CALLBACK_PREFIX}month:{month:02d}")
        for month, name in enumerate(_MONTHS[normalize_locale(locale)], 1)
    ]
    return text, [months[i:i + 3] for i in range(0, 12, 3)] + [[_back_button(locale)]]


def day_picker_view(month: int, *, locale=RU):
    # A leap year keeps February 29 available without asking for a birth year.
    days_in_month = calendar.monthrange(2000, month)[1]
    text = localized(
        locale,
        ru="🔮 <b>{month}</b>\n\nВыбери день.",
        en="🔮 <b>{month}</b>\n\nChoose a day.",
        month=_MONTHS[normalize_locale(locale)][month - 1],
    )
    days = [
        Button.inline(str(day), data=f"{CALLBACK_PREFIX}date:{day:02d}{month:02d}")
        for day in range(1, days_in_month + 1)
    ]
    return text, [days[i:i + 7] for i in range(0, len(days), 7)] + [[
        Button.inline(
            localized(locale, ru="⬅️ К месяцам", en="⬅️ Months"),
            data=f"{CALLBACK_PREFIX}months",
        ),
    ]]


async def reply_to_fortune(event, argument: str, *, bot_username: str, locale=RU):
    chosen_value = None
    if not argument:
        text, buttons = month_picker_view(locale=locale)
    else:
        try:
            code = fortune_code(argument)
            chosen_value = code if CODE_PATTERN.fullmatch(argument.strip()) else parse_fortune_date(argument)
        except ValueError:
            text = localized(
                locale,
                ru=(
                    "Пришли четыре цифры: <code>/fortune 6789</code>, "
                    "или существующую дату: <code>/fortune 21.09</code>. "
                    "Можно добавить год: <code>21.09.1990</code>; в гадании участвуют только день и месяц."
                ),
                en=(
                    "Send four digits: <code>/fortune 6789</code>, "
                    "or a valid date: <code>/fortune 21.09</code>. "
                    "You can include a year: <code>21.09.1990</code>; only the day and month are used."
                ),
            )
            buttons = [[_choose_date_button(locale)]]
        else:
            text, buttons = fortune_view(chosen_value, locale=locale)
    if not event.is_private:
        # Calendar callbacks edit private bot menus. Group replies link there
        # instead of displaying buttons the private callback router will ignore.
        open_bot = Button.url(
            localized(locale, ru="Выбрать дату в боте", en="Choose a date in the bot"),
            f"https://t.me/{bot_username}?start=img_fortune",
        )
        buttons = ([buttons[0]] if chosen_value is not None else []) + [[open_bot]]
        if not argument:
            text = localized(
                locale,
                ru="Пришли <code>/fortune 6789</code>, <code>/fortune 21.09</code> или выбери дату в личном чате с ботом.",
                en="Send <code>/fortune 6789</code>, <code>/fortune 21.09</code> or choose a date in a private chat with the bot.",
            )
    await event.reply(text, buttons=buttons, parse_mode="html", link_preview=chosen_value is not None)


def is_fortune_callback(data: str) -> bool:
    return data.startswith(CALLBACK_PREFIX)


async def handle_fortune_callback(event, *, locale=RU):
    data = event.data.decode()
    try:
        if data == f"{CALLBACK_PREFIX}months":
            text, buttons = month_picker_view(locale=locale)
        elif match := re.fullmatch(r"img_fortune:month:([0-9]{2})", data):
            month = int(match.group(1))
            if not 1 <= month <= 12:
                raise ValueError("Invalid month")
            text, buttons = day_picker_view(month, locale=locale)
        elif match := re.fullmatch(r"img_fortune:date:([0-9]{2})([0-9]{2})", data):
            chosen_date = date(2000, int(match.group(2)), int(match.group(1)))
            text, buttons = fortune_view(chosen_date, locale=locale)
        else:
            raise ValueError("Invalid fortune callback")
    except ValueError:
        await event.answer(localized(
            locale,
            ru="Эта дата не подходит. Выбери другую.",
            en="This date isn't valid. Choose another one.",
        ))
        return
    try:
        await event.edit(text, buttons=buttons, parse_mode="html", link_preview=":date:" in data)
    except MessageNotModifiedError:
        pass
    await event.answer()
