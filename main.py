import pyrogram
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums.chat_action import ChatAction
import asyncio
from random import random
from volume.config.tg_ids import dot_ch_id, beta_testers
from volume.content import startup_url, wanted_not_found
from get_hashdict import common_hashdict, alias_dict
from decorators import admin_only
from programs.radio import change_stream, get_participants, leave_group_call
from programs.other import get_bashkir_haiku, get_weather, get_minecraft_server_info
from programs.moneydrop import start_post_moneydrop_handlers
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
        open_common_hashdict("root", message, user_id)

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
        if user_id in [participant.user_id for participant in await get_participants(dot_ch_id)]:
            await change_stream(obj['radio_url'], who_called=message.from_user.id)
            return "▶️"
        return "🤷‍♂️Сначала зайди в радио!"
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
    reply_markup = InlineKeyboardMarkup(buttons)
    await app_robot.edit_message_text(
        message.chat.id,
        message.id,
        text=text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview
    )
    return None


@app_robot.on_message(pyrogram.filters.command(["start"]) & pyrogram.filters.private & pyrogram.filters.incoming)
async def start_handler(client, message):
    user_id = message.from_user.id
    new_message = await client.send_message(
        user_id,
        text="Загрузка"
    )
    deep_link = ""
    if len(message.command) >= 2:
        deep_link = message.command[1]
    return await open_common_hashdict(deep_link, new_message, user_id)


@app_robot.on_callback_query()
async def answer_common_hashdict(client, callback_query, **kwargs):
    if not callback_query.from_user.id == callback_query.message.chat.id:
        return
    answer = await open_common_hashdict(callback_query.data, callback_query.message, callback_query.from_user.id)
    if answer:
        await callback_query.answer(answer)


@app_robot.on_message(pyrogram.filters.private & pyrogram.filters.photo & pyrogram.filters.incoming)
async def answer_wanted_search(client, message):
    await asyncio.sleep(1+random())
    await client.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(2+6*random())
    await client.send_message(message.chat.id, wanted_not_found)


@app_robot.on_message(pyrogram.filters.private & (pyrogram.filters.location | pyrogram.filters.venue) & pyrogram.filters.incoming)
async def answer_location(client, message):
    match message.media:
        case pyrogram.enums.MessageMediaType.VENUE:
            location = message.venue.location
        case pyrogram.enums.MessageMediaType.LOCATION:
            location = message.location
        case _:
            raise ValueError("Unknown media type")
    await client.send_message(message.chat.id, await get_weather(location))


@app_robot.on_message(pyrogram.filters.command(["test"]) & pyrogram.filters.private)
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
    asyncio.get_event_loop().run_until_complete(start_post_moneydrop_handlers())
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
