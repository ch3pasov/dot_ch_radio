import asyncio
import logging
import os
import sys

from telethon import TelegramClient

from config.app import api_id as configured_api_id, api_hash as configured_api_hash
from libs.minimal_session import MinimalSQLiteSession

formatter = logging.Formatter('%(asctime)s %(levelname)s [%(filename)s:%(lineno)s] %(message)s')
handler_fancy_stdout = logging.StreamHandler(sys.stdout)
handler_fancy_stdout.setFormatter(formatter)
# Корневой логгер. В контейнере логи идут в Docker json-file (stdout/stderr).
root = logging.getLogger()
root.setLevel(logging.WARNING)
root.addHandler(handler_fancy_stdout)
# Логгер для красивого принта.
fancy_stdout = logging.getLogger(__name__)
fancy_stdout.setLevel(logging.INFO)
print = fancy_stdout.info

# Единый event loop для обоих клиентов и для pytgcalls.
# Создаём явно, чтобы Telethon-клиенты, pytgcalls и main.py крутились на одном loop.
try:
    loop = asyncio.get_event_loop()
    if loop.is_closed():
        raise RuntimeError("closed loop")
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

SESSION_DIR = "volume/sessions"
api_id = int(os.environ.get("TELEGRAM_API_ID") or configured_api_id)
api_hash = os.environ.get("TELEGRAM_API_HASH") or configured_api_hash

# robot_account — бот (интерфейс с inline-кнопками, callback, dice).
app_robot = TelegramClient(
    MinimalSQLiteSession(f"{SESSION_DIR}/robot_account"),
    api_id,
    api_hash,
)
# В контенте перемешаны Markdown (**bold**, [t](u), ||spoiler||) и HTML (<i>, <code>).
# По умолчанию рендерим Markdown; HTML включаем точечно через parse_mode='html'.
app_robot.parse_mode = "markdown"

# dj_account — пользователь, который ведёт групповой звонок (радио) через pytgcalls.
app_dj = TelegramClient(
    MinimalSQLiteSession(f"{SESSION_DIR}/dj_account"),
    api_id,
    api_hash,
)
