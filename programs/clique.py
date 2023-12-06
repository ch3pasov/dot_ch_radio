import sqlite3
from pyrogram.types import InlineKeyboardButton
import pyrogram
import datetime
import re

from volume.config.clique_config import clique_folder_id, clique_folder_name, initiation_phrase, description_phrase, minimum_channel_members_count, maximum_inactive_days
from global_vars import app_dj, print

connection = sqlite3.connect('/Users/anatoliy-ch/Documents/projects/dot_ch_radio/volume/database/common.db')


def get_clique_members_message():
    out = ""
    cursor = connection.cursor()
    cursor.execute("SELECT channel_emoji, channel_name, channel_username FROM clique_members ORDER BY initiation_unixtime DESC")
    for row in cursor.fetchall():
        channel_emoji, channel_name, channel_username = row
        out += f"[{channel_emoji} {channel_name}](t.me/{channel_username})\n"
    cursor.close()
    return out


def get_clique_folder_invite_link():
    cursor = connection.cursor()
    cursor.execute("""
    SELECT value FROM key_value WHERE key="clique_folder_invite_url"
    """)
    clique_folder_invite_url = cursor.fetchall()[0][0]
    cursor.close()
    return clique_folder_invite_url


def get_clique_folder_link_button():
    return [
        [
            InlineKeyboardButton(
                text="🗂 Папка с каналами",
                url=get_clique_folder_invite_link()
            )
        ]
    ]


async def update_clique_folder(connection):
    """
    Обновляет папку с каналами в телеграме, а также загружает в БД новую пригласительную ссылку.
    """
    cursor = connection.cursor()
    # собираю из базы список всех каналов

    cursor.execute("""
    SELECT channel_id FROM clique_members
    ORDER BY initiation_unixtime DESC
    """)
    rows = cursor.fetchall()
    channels = rows[0]
    channel_peers = [await app_dj.resolve_peer(channel_id) for channel_id in channels]

    # обновление состава папки

    await app_dj.invoke(
        pyrogram.raw.functions.messages.UpdateDialogFilter(
            id=2,
            filter=pyrogram.raw.types.DialogFilterChatlist(
                id=clique_folder_id,
                title=clique_folder_name,
                pinned_peers=[],
                include_peers=channel_peers,
                emoticon='👤',
            )
        )
    )

    # получение папки

    clique_folder = [
        obj for obj in (
            await app_dj.invoke(
                pyrogram.raw.functions.messages.GetDialogFilters()
            )
        )[1:] if obj.id == clique_folder_id
    ][0]

    # получение всех пригласительных ссылок

    clique_folder_invites = (
        await app_dj.invoke(
            pyrogram.raw.functions.chatlists.GetExportedInvites(
                chatlist=pyrogram.raw.types.InputChatlistDialogFilter(
                    filter_id=clique_folder.id
                )
            )
        )
    ).invites

    # удаление пригласительной ссылки (чтобы не выйти за лимит)
    if len(clique_folder_invites) > 2:
        for i in range(2):
            await app_dj.invoke(
                pyrogram.raw.functions.chatlists.DeleteExportedInvite(
                    chatlist=pyrogram.raw.types.InputChatlistDialogFilter(
                        filter_id=clique_folder.id
                    ),
                    slug=clique_folder_invites[i].url
                )
            )

    # создание ссылки на папку

    clique_folder_new_invite = (
        await app_dj.invoke(
            pyrogram.raw.functions.chatlists.ExportChatlistInvite(
                chatlist=pyrogram.raw.types.InputChatlistDialogFilter(
                    filter_id=clique_folder.id
                ),
                title=str(int(datetime.datetime.now().timestamp())),
                peers=clique_folder.include_peers
            )
        )
    ).invite

    clique_folder_new_invite_url = clique_folder_new_invite.url

    # обновление ссылки в базе

    sql = '''
    INSERT OR REPLACE INTO key_value (key, value) VALUES ('clique_folder_invite_url', ?);
    '''
    cursor.execute(sql, (clique_folder_new_invite_url,))
    cursor.close()
    connection.commit()


instuction = f"""
Чтобы ваш канал вступил в ㊙️ Клику, нужно выполнить следующие условия:
**1.** Канал должен быть открытым (иметь публичный юзернейм).
**2.** В канале должно быть не менее {minimum_channel_members_count} подписчиков.
**3.** В канале должно быть не менее 1 сообщения за последние {maximum_inactive_days} дней.
**4.** В канале должно быть не менее 1 сообщения в промежутке от {maximum_inactive_days} до {maximum_inactive_days*2} дней назад.
**5.** В описании канала должна быть фраза отдельной строчкой (скопируйте её):
`{description_phrase}`
**6.** В канале должен быть текстовый пост-инициация, без картинок. Можете написать что угодно, но в тексте должна быть волшебная фраза отдельной строчкой (скопируйте её):
`{initiation_phrase}`

Если ваш канал соответствует всем условиям и вы готовы вступить в Клику, то нажмите на кнопку ниже и приложите ссылку на пост-инициацию (пример: https://t.me/ch_an/121).
"""


def get_clique_join_instruction():
    return instuction


def validate_channel_description(channel):
    if channel.description is None:
        return False
    if re.search("^"+re.escape(description_phrase.replace("/", "\\/"))+"$", channel.description, re.MULTILINE):
        return True
    return False


def validate_initiate_message(message):
    if re.search("^"+re.escape(initiation_phrase).replace("/", "\\/")+"$", message.text, re.MULTILINE):
        return True
    return False


async def clique_registration_try(client, message, verbose=True):
    initiation_url = message.matches[0].group(1)
    print(f"registration attempt from {message.from_user.id}, {initiation_url}")

    initiation_url_match = re.search(r"^https:\/\/t\.me\/([^\/]+)\/(\d+)$", initiation_url)

    if not initiation_url_match:
        print("bad initiation url")
        return await client.send_message(message.chat.id, 'Ссылка должна соответствовать шаблону https://t.me/channel_username/123456789.')

    cursor = connection.cursor()
    cursor.execute("SELECT channel_username, owner_id FROM clique_members ORDER BY initiation_unixtime DESC")
    data = cursor.fetchall()
    existed_channel_usernames = [row[0] for row in data]
    existed_owner_ids = [row[1] for row in data]
    cursor.close()

    channel_username = initiation_url_match.group(1)
    initiation_message_id = initiation_url_match.group(2)
    owner_id = message.from_user.id

    if channel_username in existed_channel_usernames:
        print("channel already exists in clique")
        return await client.send_message(message.chat.id, "Канал уже зарегистрирован в Клике.")
    if owner_id in existed_owner_ids:
        print("owner already exists in clique")
        return await client.send_message(message.chat.id, "Вы уже зарегистрированы в Клике.")

    try:
        chat = await client.get_chat(channel_username)
    except pyrogram.errors.exceptions.bad_request_400.UsernameNotOccupied:
        print("username not occupied")
        return await client.send_message(message.chat.id, "Канала с таким именем не существует.")
    except pyrogram.errors.exceptions.bad_request_400.UsernameInvalid:
        print("username invalid")
        return await client.send_message(message.chat.id, "Неверный формат юзернейма канала.")
    except KeyError:
        print("username invalid (KeyError)")
        return await client.send_message(message.chat.id, "Из-за бага в pyrogram нельзя указать неосновной юзернейм канала. Например, для канала @ch_an/@dot_ch нужно указать @ch_an.")
    if chat.type != pyrogram.enums.ChatType.CHANNEL:
        print("not a channel")
        return await client.send_message(message.chat.id, "Это не канал.")
    channel = chat
    channel_id = channel.id

    channel_members_count = channel.members_count
    if channel_members_count < minimum_channel_members_count:
        print("not enough members")
        return await client.send_message(message.chat.id, f"В канале должно быть не менее {minimum_channel_members_count} подписчиков.")

    last_one_message = [gen async for gen in app_dj.get_chat_history(channel_id, limit=1)]
    if len(last_one_message) == 0:
        print("no messages")
        return await client.send_message(message.chat.id, "В канале должно быть не менее 1 сообщения.")
    last_message_date = last_one_message[0].date
    if last_message_date < datetime.datetime.now() - datetime.timedelta(days=maximum_inactive_days):
        print(f"last message is too old: {last_message_date}")
        return await client.send_message(message.chat.id, f"В канале должно быть не менее 1 сообщения за последние {maximum_inactive_days} дней.")
    old_last_one_message = [gen async for gen in app_dj.get_chat_history(channel_id, limit=1, offset_date=datetime.datetime.now() - datetime.timedelta(days=maximum_inactive_days*2))]
    if len(old_last_one_message) == 0:
        print("no old messages")
        return await client.send_message(message.chat.id, f"В канале должно быть не менее 1 сообщения старше {maximum_inactive_days} дней.")
    old_last_message_date = old_last_one_message[0].date
    if old_last_message_date < datetime.datetime.now() - datetime.timedelta(days=maximum_inactive_days*2):
        print(f"old last message is too old: {old_last_message_date}")
        return await client.send_message(message.chat.id, f"В канале должно быть не менее 1 сообщения в промежутке от {maximum_inactive_days} до {maximum_inactive_days*2} дней назад.")

    if not validate_channel_description(channel):
        print("bad description")
        return await client.send_message(message.chat.id, "В описании канала должна быть фраза отдельной строчкой (скопируйте её):\n`"+description_phrase+"`")

    try:
        initiation_message = await client.get_messages(channel_id, initiation_message_id)
    except pyrogram.errors.exceptions.bad_request_400.MessageIdsEmpty:
        print("message not found")
        return await client.send_message(message.chat.id, "Сообщения с таким номером не существует")
    except OverflowError:
        print("too big message id")
        return await client.send_message(message.chat.id, "Слишком большой айдишник")
    if message.empty:
        print("empty message")
        return await client.send_message(message.chat.id, "Сообщение пустое")
    if not message.text:
        print("not text message")
        return await client.send_message(message.chat.id, "Сообщение не текстовое")
    if initiation_message.forward_from_chat is not None:
        print("forwarded message")
        return await client.send_message(message.chat.id, "Пост-инициация не должна быть форвардом.")
    if validate_initiate_message(initiation_message) is False:
        print("bad initiation message")
        return await client.send_message(message.chat.id, "В пост-инициации должна быть волшебная фраза отдельной строчкой (скопируйте её):\n`"+initiation_phrase+"`")
