import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums.chat_action import ChatAction
import asyncio
from random import random
from volume.config.tg_ids import dot_ch_id, beta_testers, bot_username
from volume.content import startup_url, wanted_not_found
from get_hashdict import common_hashdict, alias_dict
from decorators import admin_only
from programs.radio import change_stream, leave_group_call  # , get_participants
from programs.other import get_bashkir_haiku, get_weather, get_minecraft_server_info, rus_to_katakana
from global_vars import app_robot, print


async def open_common_hashdict(deep_link, message, user_id):
    # refresh
    if deep_link.startswith("refresh=1=id="):
        message = await app_robot.edit_message_text(
            message.chat.id,
            message.id,
            text="refreshing...",
        )
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

    if "url" in obj or "switch_inline_query_current_chat" in obj:
        await open_common_hashdict("", message, user_id)
        return "🤷‍♂️Не знаю как ты открыл кнопку-ссылку, но ты не пройдёшь."
    # common case
    if "radio_url" in obj:

        await change_stream(obj['radio_url'], who_called=message.from_user.id)
        return "▶️"

        # if user_id in [participant.user_id for participant in await get_participants(dot_ch_id)]:
        #     await change_stream(obj['radio_url'], who_called=message.from_user.id)
        #     return "▶️"
        # return "🤷‍♂️Сначала зайди в радио!"
    buttons = []
    text = ""
    if not obj.get("hide_name", 0):
        text += f'**{obj["name"]}**'
    if "description" in obj:
        text += f'\n{obj["description"]}'
    if "children" in obj:
        children = obj["children"]
        for child in children:
            if children[child].get("beta_access", 0):
                if user_id not in beta_testers:
                    continue
            kwargs = {"text": children[child]['name']}
            if "url" in children[child]:
                kwargs["url"] = children[child]['url']
            elif "switch_inline_query_current_chat" in children[child]:
                kwargs["switch_inline_query_current_chat"] = children[child]['switch_inline_query_current_chat']
            else:
                kwargs["callback_data"] = f"id={child}"
            buttons.append([InlineKeyboardButton(**kwargs)])
    if obj.get("refresh", 0):
        buttons.append(
            [
                InlineKeyboardButton(
                    text="🔄",
                    callback_data=f"refresh=1=id={path_hash}"
                )
            ]
        )
    share_button = InlineKeyboardButton(
        text="🔗",
        # switch_inline_query=obj["share"]
        url=f"https://t.me/share/url?url={obj['share']}"
    )
    if "parent" in obj:
        parent = obj["parent"]
        buttons.append(
            [
                InlineKeyboardButton(
                    text="⬅️",
                    callback_data=f"id={parent}"
                ),
                share_button
            ]
        )
    else:
        buttons.append(
            [
                share_button
            ]
        )
    disable_web_page_preview = obj.get("disable_web_page_preview", 0)
    if "custom" in obj:
        match obj["custom"]:
            case "bashkir_haiku":
                text += f'\n{await get_bashkir_haiku()}'
            case "minecraft_server":
                text += f'\n{await get_minecraft_server_info()}'
            # case "nadezhdin":
            #     text += f'\n{await get_nadezhdin()}'
    reply_markup = InlineKeyboardMarkup(buttons)
    await app_robot.edit_message_text(
        message.chat.id,
        message.id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview
    )
    return None


async def open_common_hashdict_create(deep_link, user_id):
    new_message = await app_robot.send_message(
        user_id,
        text="Загрузка"
    )
    return await open_common_hashdict(deep_link, new_message, user_id)


@app_robot.on_message(pyrogram.filters.command(["start"]) & pyrogram.filters.private & pyrogram.filters.incoming)
async def start_handler(client, message):
    user_id = message.from_user.id
    deep_link = "root"
    if len(message.command) >= 2:
        deep_link = message.command[1]
    return await open_common_hashdict_create(deep_link, user_id)


@app_robot.on_callback_query()
async def answer_common_hashdict(client, callback_query, **kwargs):
    if not callback_query.from_user.id == callback_query.message.chat.id:
        return
    answer = await open_common_hashdict(callback_query.data, callback_query.message, callback_query.from_user.id)
    if answer:
        await callback_query.answer(answer)


# фотографии
@app_robot.on_message(pyrogram.filters.photo & pyrogram.filters.private & pyrogram.filters.incoming)
async def answer_wanted_search(client, message):
    await asyncio.sleep(1+random())
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2+6*random())
    await client.send_message(message.chat.id, wanted_not_found)
    await open_common_hashdict_create("search_wanted", message.chat.id)


# геопин
@app_robot.on_message((pyrogram.filters.location | pyrogram.filters.venue) & pyrogram.filters.private & pyrogram.filters.incoming)
async def answer_location(client, message):
    match message.media:
        case pyrogram.enums.MessageMediaType.VENUE:
            location = message.venue.location
        case pyrogram.enums.MessageMediaType.LOCATION:
            location = message.location
        case _:
            raise ValueError("Unknown media type")
    await client.send_message(message.chat.id, await get_weather(location))
    await open_common_hashdict_create("weather", message.chat.id)


# игра Василия
@app_robot.on_message(pyrogram.filters.command(["start_free_vasilii_game"]) & pyrogram.filters.private & pyrogram.filters.incoming)
async def answer_vasilii_game(client, message):
    await app_robot.send_message(
        message.chat.id,
        "Запускаю ИГРУ ВАСИЛИЯ!",
    )
    step_sleep = 0.5
    score = 0
    credit = 1000
    for i in range(100):
        await asyncio.sleep(step_sleep)
        if (await app_robot.send_dice(message.chat.id, "🎲", disable_notification=True)).dice.value <= 3:
            credit *= 0.25
            continue
        credit *= 2
        score += 1
    result_text = f"Ваш выигрыш: {credit}. Бросков с победой: {score}."
    if credit > 1000:
        result_text += " Поздравляю, королевская победа!"
        await app_robot.send_message(message.chat.id, "🥳")
    await app_robot.send_message(
        message.chat.id,
        result_text,
    )
    await app_robot.send_message(
        message.chat.id,
        "Игра окончена. Спасибо за участие!",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⬅️ Назад",
                        callback_data="vasilii_game"
                    )
                ]
            ]
        )
    )
    # await open_common_hashdict_create("vasilii_game", message.chat.id)


# rus_to_katakana
@app_robot.on_message(pyrogram.filters.regex(f'^@{bot_username} /rus_to_katakana') & pyrogram.filters.incoming)
async def answer_rus_to_katakana(client, message):
    buttons = [[InlineKeyboardButton(text="🔡 Перевести текст", switch_inline_query_current_chat="/rus_to_katakana ")]]
    if message.chat.type != pyrogram.enums.ChatType.PRIVATE:
        buttons.append([InlineKeyboardButton(text=f"🤖 К роботу", url=f"https://t.me/{bot_username}?start=rus_to_katakana")])
    relpy_markup = InlineKeyboardMarkup(buttons)
    text = message.text.lstrip(f'@{bot_username} /rus_to_katakana').lstrip(' ').lower()
    if text == "":
        message_text = "Пустой текст! Нечего переводить."
    else:
        translate_dict = await rus_to_katakana(text)
        message_text = f"<i>{translate_dict['racism']}</i>\n<code>{translate_dict['katakana']}</code>"
    await message.reply_text(
        message_text,
        quote=True,
        reply_markup=relpy_markup
    )


@app_robot.on_message(pyrogram.filters.command(["test"]) & pyrogram.filters.private & pyrogram.filters.incoming)
@admin_only
async def test_handler(client, message):
    print(message)
    # reply_markup = pyrogram.types.ReplyKeyboardMarkup(
    #     [
    #         [
    #             pyrogram.types.KeyboardButton("📍", request_location=True),
    #         ],
    #     ],
    #     resize_keyboard=True,
    #     one_time_keyboard=True,
    #     placeholder="🖖🏻🖖🏻🖖🏻🖖🏻🖖🏻"
    # )
    # reply_markup = pyrogram.types.ForceReply(
    #     selective=True,
    #     placeholder="🖖🏻🖖🏻🖖🏻🖖🏻🖖🏻"
    # )
    # await message.reply_text(
    #     "test",
    #     reply_markup=reply_markup
    # )
    pass


try:
    asyncio.get_event_loop().run_until_complete(change_stream(startup_url, who_called=''))
    pyrogram.idle()
except KeyboardInterrupt:
    print('Exiting...')
finally:
    try:
        asyncio.get_event_loop().run_until_complete(leave_group_call(dot_ch_id))
        pass
    except KeyError:
        # странная ошибка из-за того, что я залогинился через канал
        pass
