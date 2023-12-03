import sqlite3
# import re
# import datetime

connection = sqlite3.connect('/Users/anatoliy-ch/Documents/projects/dot_ch_radio/volume/database/common.db')


def get_clique_members():
    out = ""
    cursor = connection.cursor()
    cursor.execute("SELECT channel_emoji, channel_name, channel_username FROM clique_members ORDER BY initiation_unixtime DESC")
    for row in cursor.fetchall():
        channel_emoji, channel_name, channel_username = row
        out += f"[{channel_emoji} {channel_name}](t.me/{channel_username})\n"
    return out
