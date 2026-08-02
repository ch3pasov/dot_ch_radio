import asyncio
import random
from html import escape

from telethon import events, Button, utils
from telethon.tl.types import (
    DocumentAttributeVideo,
    InputMediaDice,
    MessageMediaVenue,
)

from config.tg_ids import beta_testers, bot_username
from config.debug import disable_radio
from content.content import search_sf7_custom_emoji_html, wanted_not_found
from get_hashdict import common_hashdict, alias_dict
from decorators import admin_only
from programs.radio import (
    change_stream,
    current_station_name,
    leave_group_call,
    ensure_startup_stream,
    start_calls,
)
from programs.night_schedule import (
    NIGHT_RADIO_SWITCH_BLOCKED,
    is_night_radio_lockout_utc,
    radio_now_playing_text,
)
from programs.other import get_bashkir_haiku, get_weather_response, get_minecraft_server_info, rus_to_katakana, invert_picture, get_turkic_name
from programs.video_inversion import VideoInversionError, invert_video_note
from programs.data_rights import (
    handle_data_rights_callback,
    is_data_rights_callback,
)
from libs.message_effects import load_message_effects
from libs.telegram_delivery import (
    deliver_message,
    deliver_video_note_with_fallback,
)
from libs.telegram_navigation import (
    answer_refresh_callback,
    is_refresh_callback,
    unwrap_refresh_callback,
)
from libs.telegram_ui import build_button, build_child_rows
from config.tg_ids import dot_ch_id
from global_vars import app_robot, app_dj, loop, print

MENTION = f"@{bot_username}"


def _page_title(obj, parse_mode):
    """Render a page title, optionally prefixed with a custom Telegram emoji."""

    title_icon = obj.get("title_icon")
    if title_icon is None:
        if parse_mode == "html":
            return f'<b>{escape(obj["name"])}</b>'
        return f'**{obj["name"]}**'

    if parse_mode != "html":
        raise ValueError("title_icon requires parse_mode='html'")
    return (
        f'<tg-emoji emoji-id="{title_icon}">🗄</tg-emoji> '
        f'<b>{escape(obj["name"])}</b>'
    )


def _is_private(event) -> bool:
    return bool(getattr(event, "is_private", False))


def _not_channel(event) -> bool:
    # Исключаем сообщения из broadcast-канала.
    return not (getattr(event, "is_channel", False) and not getattr(event, "is_group", False))


async def _node_telegram_media(obj):
    file_id = obj.get("telegram_file_id")
    if not file_id:
        return None
    media = utils.resolve_bot_file_id(file_id)
    if media is None:
        print(f"failed to resolve telegram file_id for {obj.get('name')}")
    return media


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
            "callback_data",
        )
    )


def _child_button_rows(children, obj, user_id):
    return build_child_rows(
        children,
        columns=obj.get("children_columns", 1),
        include=lambda _child_hash, child: not child.get("beta_access", 0)
        or user_id in beta_testers,
    )


def _navigation_ui():
    return common_hashdict[alias_dict["root"]]["navigation_ui"]


def _data_rights_ui():
    return common_hashdict[alias_dict["my_data"]]


async def _roll(chat_id, emoticon):
    m = await app_robot.send_file(chat_id, InputMediaDice(emoticon), silent=True)
    return m.media.value


async def open_common_hashdict(deep_link, message, user_id):
    deep_link = unwrap_refresh_callback(deep_link)

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
            if message is None:
                await open_common_hashdict("radio", None, user_id)
            return NIGHT_RADIO_SWITCH_BLOCKED
        await change_stream(obj['radio_url'], who_called="menu")
        if message is None:
            await open_common_hashdict("radio", None, user_id)
        else:
            parent_hash = obj.get("parent")
            parent = common_hashdict.get(parent_hash, {})
            if parent.get("custom") == "radio_now_playing":
                await open_common_hashdict(f"id={parent_hash}", message, user_id)
        return "▶️"

    buttons = []
    text = ""
    parse_mode = obj.get("parse_mode", ())
    if not obj.get("hide_name", 0):
        text += _page_title(obj, parse_mode)
    if "description" in obj:
        text += f'\n{obj["description"]}'
    if "children" in obj:
        buttons.extend(_child_button_rows(obj["children"], obj, user_id))
    navigation_ui = _navigation_ui()
    if obj.get("refresh", 0):
        buttons.append(
            [
                build_button(
                    navigation_ui["refresh"],
                    default_callback_data=f"refresh=1=id={path_hash}",
                )
            ]
        )
    share_button = build_button(
        navigation_ui["share"],
        default_url=f"https://t.me/share/url?url={obj['share']}",
    )
    if "parent" in obj:
        parent = obj["parent"]
        buttons.append(
            [
                build_button(
                    navigation_ui["back"],
                    default_callback_data=f"id={parent}",
                ),
                share_button,
            ]
        )
    else:
        buttons.append([share_button])
    disable_web_page_preview = obj.get("disable_web_page_preview", 0)
    if "custom" in obj:
        match obj["custom"]:
            case "radio_now_playing":
                text += f'\n\n{radio_now_playing_text(station_name=current_station_name())}'
            case "bashkir_haiku":
                text += f'\n{await get_bashkir_haiku()}'
            case "minecraft_server":
                text += f'\n{await get_minecraft_server_info()}'
    telegram_media = await _node_telegram_media(obj)
    return await deliver_message(
        app_robot,
        message,
        user_id,
        text,
        buttons=buttons,
        link_preview=not disable_web_page_preview,
        file=telegram_media,
        parse_mode=parse_mode,
    )


async def open_common_hashdict_create(deep_link, user_id):
    async with app_robot.action(user_id, "typing"):
        return await open_common_hashdict(deep_link, None, user_id)


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
    if is_data_rights_callback(data):
        result = await handle_data_rights_callback(event, app_robot, _data_rights_ui())
        if result == "home":
            msg = await event.get_message()
            await open_common_hashdict("my_data", msg, event.sender_id)
        return
    refresh_callback = is_refresh_callback(data)
    msg = await event.get_message()
    answer = await open_common_hashdict(data, msg, event.sender_id)
    if refresh_callback:
        await answer_refresh_callback(event, answer)
    elif isinstance(answer, str) and answer:
        await event.answer(answer)
    else:
        await event.answer()


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
        markup = [[Button.url("🤖 К роботу", f"https://t.me/{bot_username}?start=inversion")]]

    # Telegram has no download/processing action, so "typing" truthfully represents
    # preparing the reply. The CPU-heavy transform runs outside the event loop.
    async with app_robot.action(event.chat_id, "typing"):
        photo = await message_with_content.download_media(file=bytes)
        processed_photo_bytes = await invert_picture(photo)

    # Use Telegram's native upload animation with real byte progress.
    async with app_robot.action(event.chat_id, "photo") as upload_action:
        await app_robot.send_file(
            event.chat_id,
            processed_photo_bytes,
            reply_to=event.message.id,
            buttons=markup,
            allow_cache=False,
            progress_callback=upload_action.progress,
        )


async def answer_invert_video_note_common(event, message_with_content):
    if event.is_private:
        markup = [[Button.switch_inline(
            "🔘 Инвертировать ещё кружочек",
            query="invert_video_note (пришли кружочек роботу)",
            same_peer=True,
        )]]
    else:
        markup = [[Button.url(
            "🤖 К роботу",
            f"https://t.me/{bot_username}?start=inversion",
        )]]

    status_message = await event.reply("🙏 Получил кружочек, готовлю инверсию.")
    try:
        async with app_robot.action(event.chat_id, "record-round"):
            video_note = await message_with_content.download_media(file=bytes)
            if not video_note:
                raise VideoInversionError("Telegram returned no video data.")
            await status_message.edit("🌚 Инвертирую кружочек.")
            processed_video_note = await invert_video_note(video_note)
    except VideoInversionError:
        await status_message.edit("😔 Не получилось инвертировать этот кружочек.")
        return

    def video_attribute(*, round_message):
        return [DocumentAttributeVideo(
            duration=processed_video_note.duration,
            w=processed_video_note.width,
            h=processed_video_note.height,
            round_message=round_message,
            supports_streaming=True,
        )]

    async def send_video_note():
        async with app_robot.action(event.chat_id, "round") as upload_action:
            return await app_robot.send_file(
                event.chat_id,
                processed_video_note,
                reply_to=event.message.id,
                buttons=markup,
                allow_cache=False,
                progress_callback=upload_action.progress,
                supports_streaming=True,
                video_note=True,
                mime_type="video/mp4",
                attributes=video_attribute(round_message=True),
            )

    async def send_video():
        privacy_explanation = (
            "🔒 Telegram запретил боту прислать тебе видеокружок.\n\n"
            "Чтобы разрешить: Настройки → Конфиденциальность → Голосовые "
            f"сообщения. Добавь {MENTION} в «Всегда разрешать» или выбери «Все».\n\n"
            "Кнопка ниже откроет нужный раздел. Пока отправляю обычным видео."
        )
        privacy_markup = [[Button.url(
            "⚙️ Настройки голосовых",
            "tg://settings/privacy/voice",
        )], *markup]
        await status_message.edit(privacy_explanation)
        async with app_robot.action(event.chat_id, "video") as upload_action:
            return await app_robot.send_file(
                event.chat_id,
                processed_video_note,
                caption=privacy_explanation,
                reply_to=event.message.id,
                buttons=privacy_markup,
                allow_cache=False,
                progress_callback=upload_action.progress,
                supports_streaming=True,
                video_note=False,
                mime_type="video/mp4",
                attributes=video_attribute(round_message=False),
            )

    try:
        await deliver_video_note_with_fallback(
            processed_video_note,
            send_video_note=send_video_note,
            send_video=send_video,
        )
    except Exception:
        await status_message.edit(
            "😔 Инверсия готова, но Telegram не принял результат."
        )
        raise
    else:
        await status_message.delete()


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


# A private video note is an explicit request. In groups the feature is only
# activated by replying to a note with a mention, so ordinary chat is untouched.
@app_robot.on(events.NewMessage(
    incoming=True,
    func=lambda e: e.video_note is not None and _is_private(e),
))
async def answer_invert_video_note(event):
    await answer_invert_video_note_common(event, event.message)
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
    if reply and reply.video_note:
        # инвертировать видеокружок собеседника
        return await answer_invert_video_note_common(event, reply)
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
    await app_robot.send_message(
        event.chat_id,
        await get_weather_response(geo.lat, geo.long),
    )
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
    print("admin invoked /test")


async def amain():
    print('login in dj account')
    await app_dj.start()
    effects_count = await load_message_effects(app_dj)
    print(f"loaded {effects_count} non-premium message effects")
    print('login in robot account')
    await app_robot.start()
    if not disable_radio:
        await start_calls()
    await ensure_startup_stream()
    me = await app_robot.get_me()
    print(f"running as @{getattr(me, 'username', None)}")
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
