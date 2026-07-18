"""Безопасная проверка Telethon-сессий: подключиться, get_me() и отключиться.

НЕ запускает обработчики и НЕ заходит в войс-чат — только проверяет, что
Telethon-сессии авторизованы. Безопасно для прод-аккаунтов.

Запуск (внутри контейнера, из каталога проекта):
    python scripts/check_login.py
"""
import asyncio
import os

from telethon import TelegramClient

from config.app import api_id as configured_api_id, api_hash as configured_api_hash

SESSION_DIR = "volume/sessions"
api_id = int(os.environ.get("TELEGRAM_API_ID") or configured_api_id)
api_hash = os.environ.get("TELEGRAM_API_HASH") or configured_api_hash


async def check(name: str):
    client = TelegramClient(f"{SESSION_DIR}/{name}", api_id, api_hash)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            print(f"[FAIL] {name}: не авторизован")
            return False
        me = await client.get_me()
        print(f"[ OK ] {name}: id={me.id} username=@{me.username} bot={me.bot}")
        return True
    finally:
        await client.disconnect()


async def main():
    r1 = await check("robot_account")
    r2 = await check("dj_account")
    return r1 and r2


if __name__ == "__main__":
    ok = asyncio.get_event_loop().run_until_complete(main())
    raise SystemExit(0 if ok else 1)
