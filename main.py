import asyncio
import random

from telethon import events, Button, utils
from telethon.errors import MessageNotModifiedError, ReplyMarkupTooLongError
from telethon.tl.types import (
    InputMediaDice,
    KeyboardButtonCopy,
    KeyboardButtonSimpleWebView,
    KeyboardButtonUserProfile,
    KeyboardButtonWebView,
    MessageMediaVenue,
)

from config.tg_ids import beta_testers, bot_username
from config.debug import disable_radio
from content.content import search_sf7_custom_emoji_html, wanted_not_found
from get_hashdict import common_hashdict, alias_dict
from decorators import admin_only
from programs.radio import (
    change_stream,
    leave_group_call,
    ensure_startup_stream,
    start_calls,
)
from programs.night_schedule import is_night_radio_lockout_utc, NIGHT_RADIO_SWITCH_BLOCKED
from programs.other import get_bashkir_haiku, get_weather, get_minecraft_server_info, rus_to_katakana, invert_picture, get_turkic_name
from config.tg_ids import dot_ch_id
from global_vars import app_robot, app_dj, loop, print

MENTION = f"@{bot_username}"


def _is_private(event) -> bool:
    return bool(getattr(event, "is_private", False))


def _not_channel(event) -> bool:
    # Исключаем сообщения из broadcast-канала.
    return not (getattr(event, "is_channel", False) and not getattr(event, "is_group", False))


async def _safe_edit(message, text, *, buttons=None, link_preview=True, file=None, parse_mode=()):
    try:
        return await message.edit(
            text,
            buttons=buttons or None,
            link_preview=link_preview,
            file=file,
            parse_mode=parse_mode,
        )
    except MessageNotModifiedError:
        return message
    except ReplyMarkupTooLongError:
        fallback = (
            f"{text}\n\n"
            "⚠️ Не смог отрисовать клавиатуру: Telegram отклонил слишком большую разметку."
        )
        return await message.edit(fallback, buttons=None, link_preview=link_preview, parse_mode=parse_mode)


async def _node_telegram_media(obj):
    file_id = obj.get("telegram_file_id")
    if not file_id:
        return None
    media = utils.resolve_bot_file_id(file_id)
    if media is None:
        print(f"failed to resolve telegram file_id for {obj.get('name')}")
    return media


def _button_label(item):
    return item.get("button_text") or item["name"]


def _button_icon(item):
    icon = item.get("button_icon")
    return int(icon) if icon is not None else None


def _button_style(item):
    return item.get("button_style")


def _raw_button_style(item):
    return Button._get_style(_button_style(item), _button_icon(item))


def _child_is_action_button(item):
    return any(
        key in item
        for key in (
            "url",
            "switch_inline_query",
            "switch_inline_query_current_chat",
            "copy_text",
            "web_app_url",
            "simple_web_app_url",
            "user_id",
        )
    )


def _build_child_button(child_hash, item):
    label = _button_label(item)
    style = _button_style(item)
    icon = _button_icon(item)

    if "url" in item:
        return Button.url(label, item["url"], style=style, icon=icon)
    if "copy_text" in item:
        return KeyboardButtonCopy(label, item["copy_text"], style=_raw_button_style(item))
    if "web_app_url" in item:
        return KeyboardButtonWebView(label, item["web_app_url"], style=_raw_button_style(item))
    if "simple_web_app_url" in item:
        return KeyboardButtonSimpleWebView(label, item["simple_web_app_url"], style=_raw_button_style(item))
    if item.get("button_type") == "user_profile" or "user_id" in item:
        return KeyboardButtonUserProfile(label, int(item["user_id"]), style=_raw_button_style(item))
    if "switch_inline_query_current_chat" in item:
        return Button.switch_inline(
            label,
            query=item["switch_inline_query_current_chat"],
            same_peer=True,
            style=style,
            icon=icon,
        )
    if "switch_inline_query" in item:
        return Button.switch_inline(
            label,
            query=item["switch_inline_query"],
            same_peer=bool(item.get("same_peer", False)),
            style=style,
            icon=icon,
        )
    return Button.inline(label, data=f"id={child_hash}", style=style, icon=icon)


def _child_button_rows(children, obj, user_id):
    columns = max(1, int(obj.get("children_columns", 1)))
    rows = []
    row = []

    for child_hash, child in children.items():
        if child.get("beta_access", 0) and user_id not in beta_testers:
            continue

        if child.get("break_before") and row:
            rows.append(row)
            row = []

        row.append(_build_child_button(child_hash, child))

        if child.get("break_after") or len(row) >= columns:
            rows.append(row)
            row = []

    if row:
        rows.append(row)
    return rows


async def _roll(chat_id, emoticon):
    m = await app_robot.send_file(chat_id, InputMediaDice(emoticon), silent=True)
    return m.media.value


async def open_common_hashdict(deep_link, message, user_id):
    # refresh
    if deep_link.startswith("refresh=1=id="):
        message = await _safe_edit(message, "refreshing...")
        await asyncio.sleep(1)
        return await open_common_hashdict(deep_link[10:], message, user_id)

    if deep_link == "":
        return await open_common_hashdict("root", message, user_id)

    # id=
    path_hash = deep_link[3:]
    if not deep_link.startswith("id="):
        # aliases
        path_hash = "ERROR"
        if deep_link in alias_dict:
            path_hash = alias_dict[deep_link]

    # error
    if path_hash not in common_hashdict:
        await open_common_hashdict("", message, user_id)
        return "😬 битая кнопка"

    obj = common_hashdict[path_hash]
    # beta access
    if obj.get("beta_access", 0):
        if user_id not in beta_testers:
            await open_common_hashdict("", message, user_id)
            return "🤷‍♂️Не знаю как ты это открыл, но тебе сюда нельзя."

    if _child_is_action_button(obj):
        await open_common_hashdict("", message, user_id)
        return "🤷‍♂️Не знаю как ты открыл action-кнопку, но ты не пройдёшь."
    # common case
    if "radio_url" in obj:
        if is_night_radio_lockout_utc():
            return NIGHT_RADIO_SWITCH_BLOCKED
        await change_stream(obj['radio_url'], who_called=user_id)
        return "▶️"

    buttons = []
    text = ""
    if not obj.get("hide_name", 0):
        text += f'**{obj["name"]}**'
    if "description" in obj:
        text += f'\n{obj["description"]}'
    if "children" in obj:
        buttons.extend(_child_button_rows(obj["children"], obj, user_id))
    if obj.get("refresh", 0):
        buttons.append([Button.inline("🔄", data=f"refresh=1=id={path_hash}")])
    share_button = Button.url("🔗", f"https://t.me/share/url?url={obj['share']}")
    if "parent" in obj:
        parent = obj["parent"]
        buttons.append([Button.inline("⬅️", data=f"id={parent}"), share_button])
    else:
        buttons.append([share_button])
    disable_web_page_preview = obj.get("disable_web_page_preview", 0)
    if "custom" in obj:
        match obj["custom"]:
            case "bashkir_haiku":
                text += f'\n{await get_bashkir_haiku()}'
            case "minecraft_server":
                text += f'\n{await get_minecraft_server_info()}'
            # case "nadezhdin":
            #     text += f'\n{await get_nadezhdin()}'
    telegram_media = await _node_telegram_media(obj)
    await _safe_edit(
        message,
        text,
        buttons=buttons,
        link_preview=not disable_web_page_preview,
        file=telegram_media,
        parse_mode=obj.get("parse_mode", ()),
    )
    return None


async def open_common_hashdict_create(deep_link, user_id):
    new_message = await app_robot.send_message(user_id, "Загрузка")
    return await open_common_hashdict(deep_link, new_message, user_id)


@app_robot.on(events.NewMessage(pattern=r'^/start(?:\s+(\S+))?\s*$', incoming=True, func=_is_private))
async def start_handler(event):
    user_id = event.sender_id
    arg = event.pattern_match.group(1)
    deep_link = arg if arg else "root"
    await open_common_hashdict_create(deep_link, user_id)
    raise events.StopPropagation


@app_robot.on(events.CallbackQuery())
async def answer_common_hashdict(event):
    if event.sender_id != event.chat_id:
        return
    data = event.data.decode()
    msg = await event.get_message()
    answer = await open_common_hashdict(data, msg, event.sender_id)
    if answer:
        await event.answer(answer)


async def answer_rus_to_katakana_common(event, message_with_content):
    if event.is_private:
        markup = [[Button.switch_inline("🔡 Перевести текст", query="rus_to_katakana ", same_peer=True)]]
    else:
        markup = [[Button.url("🤖 К роботу", f"https://t.me/{bot_username}?start=rus_to_katakana")]]

    text = (message_with_content.raw_text or "").removeprefix(MENTION).removeprefix(' rus_to_katakana').lstrip(' ').lower()
    translate_dict = await rus_to_katakana(text)
    message_text = f"<i>{translate_dict['racism']}</i>\n<code>{translate_dict['katakana']}</code>"

    await event.reply(message_text, buttons=markup, parse_mode='html')


# rus_to_katakana by command
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: _not_channel(e) and (e.raw_text or "").startswith(f"{MENTION} rus_to_katakana"),
))
async def answer_rus_to_katakana(event):
    await answer_rus_to_katakana_common(event, event.message)
    raise events.StopPropagation


# поиск в розыске
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: _is_private(e) and e.photo is not None and (e.raw_text or "").startswith(f"{MENTION} search_wanted"),
))
async def answer_wanted_search(event):
    await asyncio.sleep(1 + random.random())
    async with app_robot.action(event.chat_id, 'typing'):
        await asyncio.sleep(2 + 6 * random.random())
    await app_robot.send_message(event.chat_id, wanted_not_found)
    await open_common_hashdict_create("search_wanted", event.chat_id)
    raise events.StopPropagation


@app_robot.on(events.NewMessage(
    pattern=r'^(?:@dot_ch_bot\s+)?/sf7_search_([a-z]+)(?:@\w+)?(?:\s+(.+))?$',
    incoming=True,
    func=lambda e: _not_channel(e),
))
async def answer_sf7_custom_emoji_search(event):
    weight_slug = event.pattern_match.group(1)
    query = event.pattern_match.group(2) or ""
    message_text = search_sf7_custom_emoji_html(weight_slug, query)
    search_query = f"/sf7_search_{weight_slug} {query}".rstrip()
    markup = [[Button.switch_inline("🔎 Искать SF7", query=f"{search_query} ", same_peer=True)]]
    if message_text is None:
        await event.reply("Не знаю такую толщину SF7.", buttons=markup)
    else:
        await event.reply(message_text, buttons=markup, parse_mode="html")
    raise events.StopPropagation


all_answers = [
    # yes
    "Насколько я вижу да", "Это бесспорно", "Да это так", "Мои источники говорят да", "ДА!",
    "Определённо да", "Перспектива хорошая", "Знаки указывают что да", "Без сомнения",
    "Ты можешь надеяться на это", "Наиболее вероятно",
    # no
    "Не рассчитывай на это", "Я так не думаю", "Мои источники говорят нет", "НЕТ!",
    "Перспектива не очень хорошая", "Знаки указывают что нет", "Извини, нет",
    "Я сомневаюсь насчёт этого", "Очень сомневаюсь",
    # idk
    "Спроси позже", "Лучше сейчас не говорить тебе", "Не могу сейчас сказать",
    "Соберись с мыслями и спроси снова", "Будущее туманно спроси позже", "Может быть"
]


async def answer_gork(event):
    message_text = random.choice(all_answers)
    print(message_text)
    return await event.reply(message_text)


async def answer_invert_picture_common(event, message_with_content):
    if event.is_private:
        markup = [[Button.switch_inline("🔘 Инвертировать картинку", query="invert_picture (приложи фотографию к этому сообщению и отправляй)", same_peer=True)]]
    else:
        markup = [[Button.url("🤖 К роботу", f"https://t.me/{bot_username}?start=invert_picture")]]

    reply_message = await event.reply("🙏 Получил запрос, ждите (долго).")
    # Скачиваем фото в оперативную память
    photo = await message_with_content.download_media(file=bytes)
    await reply_message.edit("🌚 Скачал фотку, ждите (тоже долго).")
    processed_photo_bytes = await invert_picture(photo)
    # Отправляем обработанное фото
    await event.reply(file=processed_photo_bytes, buttons=markup)
    await reply_message.delete()


# invert_picture by command or directly in chat
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: e.photo is not None and _not_channel(e) and (
        e.is_private or (e.raw_text or "").startswith(f"{MENTION} invert_picture")
    ),
))
async def answer_invert_picture(event):
    await answer_invert_picture_common(event, event.message)
    raise events.StopPropagation


# mention
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: _not_channel(e) and (e.raw_text or "").startswith(MENTION),
))
async def answer_invert_mention(event):
    reply = await event.get_reply_message()
    text = event.raw_text or ""
    command_text = text.removeprefix(MENTION).lstrip(' ')
    if command_text.startswith("/sf7_search_"):
        return
    # ответ от имени канала
    if getattr(event.message, "post", False) or (event.sender_id is not None and event.sender_id < 0):
        return await event.reply("💩")
    if reply and text.removeprefix(MENTION).lstrip(' ').lower().startswith("is this true"):
        # ответ на "is this true"
        return await answer_gork(event)
    if event.photo:
        # инвертировать фотку
        return await answer_invert_picture_common(event, event.message)
    if reply and reply.photo:
        # инвертировать фотку собеседника
        return await answer_invert_picture_common(event, reply)
    if text.removeprefix(MENTION).lstrip(' ') != "":
        # перевести текст в катакану
        return await answer_rus_to_katakana_common(event, event.message)
    if reply and (reply.raw_text or "").removeprefix(MENTION).lstrip(' ') != "":
        # перевести текст собеседника в катакану
        sender = await reply.get_sender()
        if sender is not None and getattr(sender, "username", None) == bot_username:
            return await event.reply("😝")
        return await answer_rus_to_katakana_common(event, reply)
    await event.reply("🤷‍♂️ Не понимаю")


# геопин
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: _is_private(e) and (getattr(e.message, "geo", None) is not None or isinstance(e.message.media, MessageMediaVenue)),
))
async def answer_location(event):
    media = event.message.media
    if isinstance(media, MessageMediaVenue):
        geo = media.geo
    else:
        geo = event.message.geo
    await app_robot.send_message(event.chat_id, await get_weather(geo.lat, geo.long))
    await open_common_hashdict_create("weather", event.chat_id)
    raise events.StopPropagation


# тюркское имя
@app_robot.on(events.NewMessage(pattern=r'^/start_turkic_name_game(?:\s|$)', incoming=True, func=_is_private))
async def answer_tirkic_name_game(event):
    chat_id = event.chat_id
    roll_1 = (await _roll(chat_id, "🎲")) - 1
    roll_2 = (await _roll(chat_id, "🎲")) - 1
    roll_slot = (await _roll(chat_id, "🎰")) - 1
    turkic_name_out = get_turkic_name(roll_1, roll_2, roll_slot)

    await asyncio.sleep(4)

    await app_robot.send_message(
        chat_id,
        turkic_name_out["message_text"],
        buttons=[[Button.url("🔤 Поделиться именем", turkic_name_out["share_url"])]],
    )
    await open_common_hashdict_create("turkic_names", chat_id)
    raise events.StopPropagation


# игра Василия
@app_robot.on(events.NewMessage(pattern=r'^/start_free_vasilii_game(?:\s|$)', incoming=True, func=_is_private))
async def answer_vasilii_game(event):
    chat_id = event.chat_id
    await app_robot.send_message(chat_id, "Запускаю ИГРУ ВАСИЛИЯ!")
    step_sleep = 0.5
    score = 0
    credit = 1000
    for i in range(100):
        await asyncio.sleep(step_sleep)
        if (await _roll(chat_id, "🎲")) <= 3:
            credit *= 0.25
            continue
        credit *= 2
        score += 1
    result_text = f"Ваш выигрыш: {credit}. Бросков с победой: {score}."
    if credit > 1000:
        result_text += " Поздравляю, королевская победа!"
        await app_robot.send_message(chat_id, "🥳")
    await app_robot.send_message(chat_id, result_text)
    await app_robot.send_message(
        chat_id,
        "Игра окончена. Спасибо за участие!",
        buttons=[[Button.inline("⬅️ Назад", data="vasilii_game")]],
    )
    raise events.StopPropagation


@app_robot.on(events.NewMessage(pattern=r'^/test(?:\s|$)', incoming=True, func=_is_private))
@admin_only
async def test_handler(event):
    print(event.message.stringify())


async def amain():
    print('login in dj account')
    await app_dj.start()
    print('login in robot account')
    await app_robot.start()
    if not disable_radio:
        await start_calls()
    await ensure_startup_stream()
    me = await app_robot.get_me()
    print(f"running as @{getattr(me, 'username', None)} (id={getattr(me, 'id', None)})")
    await app_robot.run_until_disconnected()


if __name__ == "__main__":
    try:
        loop.run_until_complete(amain())
    except KeyboardInterrupt:
        print('Exiting...')
    finally:
        try:
            loop.run_until_complete(leave_group_call(dot_ch_id))
        except Exception:
            pass
