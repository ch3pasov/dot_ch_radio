import sqlite3
from pyrogram.types import InlineKeyboardButton
import pyrogram
import datetime

connection = sqlite3.connect('/Users/anatoliy-ch/Documents/projects/dot_ch_radio/volume/database/common.db')


def get_clique_members():
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


async def update_clique_folder(connection, app_dj):
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
                id=2,
                title='[㊙️]',
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
        )[1:] if obj.title == '[㊙️]'
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
