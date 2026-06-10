"""Конвертация Pyrogram-сессий (.session, SQLite) в формат Telethon, без повторного логина.

Pyrogram и Telethon хранят авторизацию в разных SQLite-схемах, но сам auth_key
привязан к аккаунту+DC, а не к библиотеке. Поэтому достаточно перенести (dc_id, auth_key).

Запуск (внутри контейнера, где установлен telethon), из каталога проекта:
    python scripts/convert_sessions.py

Исходные .session бэкапятся в <name>.session.pyrogram.bak, затем перезаписываются
telethon-форматом под тем же именем (его и открывает TelegramClient).
"""
import os
import shutil
import sqlite3
import sys

from telethon.sessions import SQLiteSession
from telethon.crypto import AuthKey

# Боевые IP дата-центров Telegram (Telethon мигрирует сам, но корректный IP ускоряет первый коннект).
DC_IP = {
    1: "149.154.175.53",
    2: "149.154.167.51",
    3: "149.154.175.100",
    4: "149.154.167.91",
    5: "91.108.56.130",
}

SESSIONS_DIR = os.environ.get("SESSIONS_DIR", "volume/sessions")
NAMES = ["robot_account", "dj_account"]


def is_pyrogram_session(path: str) -> bool:
    try:
        con = sqlite3.connect(path)
        cur = con.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}
        # Pyrogram: sessions(dc_id, api_id, auth_key, ...) + peers; Telethon: sessions(dc_id, server_address, port, auth_key) + entities
        cur.execute("PRAGMA table_info(sessions)")
        cols = {r[1] for r in cur.fetchall()}
        con.close()
        return "peers" in tables and "auth_key" in cols and "server_address" not in cols
    except Exception:
        return False


def read_pyrogram(path: str):
    con = sqlite3.connect(path)
    dc_id, auth_key = con.execute("SELECT dc_id, auth_key FROM sessions").fetchone()
    con.close()
    return int(dc_id), bytes(auth_key)


def convert_one(name: str) -> bool:
    base = os.path.join(SESSIONS_DIR, name)
    session_file = base + ".session"

    if not os.path.isfile(session_file):
        print(f"[skip] {session_file}: нет файла")
        return False

    if not is_pyrogram_session(session_file):
        print(f"[skip] {session_file}: не Pyrogram-сессия (возможно, уже Telethon)")
        return False

    dc_id, auth_key = read_pyrogram(session_file)
    if len(auth_key) != 256:
        print(f"[err ] {session_file}: неожиданная длина auth_key {len(auth_key)}")
        return False

    backup = session_file + ".pyrogram.bak"
    shutil.copy2(session_file, backup)
    print(f"[bak ] {session_file} -> {backup}")

    # Убираем старый pyrogram-файл и его журналы, чтобы Telethon создал чистую схему.
    for suffix in (".session", ".session-journal", ".session-wal", ".session-shm"):
        p = base + suffix
        if os.path.isfile(p):
            os.remove(p)

    sess = SQLiteSession(base)  # создаст base + ".session" в telethon-схеме
    sess.set_dc(dc_id, DC_IP.get(dc_id, DC_IP[2]), 443)
    sess.auth_key = AuthKey(auth_key)
    sess.save()
    sess.close()
    print(f"[ok  ] {session_file}: telethon-сессия записана (dc_id={dc_id})")
    return True


def main():
    ok = 0
    for name in NAMES:
        if convert_one(name):
            ok += 1
    print(f"Готово: сконвертировано {ok} из {len(NAMES)}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
