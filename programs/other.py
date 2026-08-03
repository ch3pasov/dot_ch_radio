import asyncio
import io
import os
import re
from typing import Any, Dict, Tuple
from urllib.parse import quote

import aiohttp
import numpy as np
from PIL import Image

from config.minecraft_config import server_url
from libs.i18n import RU, localized, normalize_locale


async def aiohttp_get(url, type='text', *, params=None):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as resp:
            match type:
                case 'text':
                    return await resp.text()
                case 'json':
                    return await resp.json()
                case _:
                    raise ValueError("Unknown type")


async def aiohttp_get_text(url) -> str:
    return await aiohttp_get(url, 'text')


async def aiohttp_get_json(url, *, params=None) -> Dict[str, Any]:
    result = await aiohttp_get(url, 'json', params=params)
    if not isinstance(result, dict):
        raise TypeError(f"Expected a dict, got {type(result).__name__}")
    return result


async def get_bashkir_haiku():
    return "\n".join(
        re.findall(
            r'<span[^>]*>\s*([^<]+?)\s*</span>',
            (await aiohttp_get_text('http://nevmenandr.net/cgi-bin/haiku.html')).split("<table>\n")[1].split("\n</table>")[0],
        )
    )


async def get_weather(lat, lon, *, locale=RU):
    api_key = os.environ.get('OPENWEATHER_API_KEY')
    if not api_key:
        raise RuntimeError(localized(
            locale,
            ru='Погода недоступна: OpenWeather API не настроен.',
            en='Weather is unavailable: the OpenWeather API is not configured.',
        ))

    try:
        weather_data: Dict[str, Any] = await aiohttp_get_json(
            'https://api.openweathermap.org/data/2.5/weather',
            params={
                'lat': lat,
                'lon': lon,
                'units': 'metric',
                'lang': normalize_locale(locale),
                'appid': api_key,
            },
        )
    except (aiohttp.ClientError, asyncio.TimeoutError):
        weather_data = None

    if weather_data is None:
        raise RuntimeError(localized(
            locale,
            ru='Не удалось получить погоду от OpenWeather.',
            en='OpenWeather did not return the weather.',
        )) from None

    temperature = weather_data['main']['temp']
    temperature_feels = weather_data['main']['feels_like']
    wind_speed = weather_data['wind']['speed']

    return localized(
        locale,
        ru=(
            "В {place} {temperature}℃\n"
            "Ощущается как {feels_like}℃\n"
            "Скорость ветра {wind_speed}м/с"
        ),
        en=(
            "{place}: {temperature}℃\n"
            "Feels like {feels_like}℃\n"
            "Wind speed: {wind_speed} m/s"
        ),
        place=weather_data['name'],
        temperature=str(temperature),
        feels_like=temperature_feels,
        wind_speed=wind_speed,
    )


WEATHER_UNAVAILABLE_MESSAGE = (
    "Не получилось получить погоду. Попробуйте отправить геопозицию ещё раз чуть позже."
)


async def get_weather_response(lat, lon, *, locale=RU):
    try:
        return await get_weather(lat, lon, locale=locale)
    except RuntimeError:
        return localized(
            locale,
            ru=WEATHER_UNAVAILABLE_MESSAGE,
            en="Couldn't get the weather. Please send the location again a little later.",
        )


minecaft_server_info = """Присоединяйтесь к нашему Minecraft серверу!

Адрес java-сервера: `{server_url}`

Правил всего лишь 3:
**1.** Все правила Российской Федерации (не убей, не кради, не разжигай, etc)
**2.** Не используй софт\\моды, дающие игровое преимущество.
**3.** Не испытывай сервер на прочность.

Статус сервера: {status}
"""
status_online = """**Онлайн**
{description}
Версия **{version_name}**
Игроков: **{players_online}/{players_max}**
{players_list}
"""
status_offline = """**Оффлайн**"""


async def get_minecraft_server_info(*, locale=RU):
    response = await aiohttp_get_json(f'https://api.mcsrvstat.us/2/{server_url}')
    if not response['online']:
        status = localized(locale, ru=status_offline, en="**Offline**")
    else:
        status = localized(
            locale,
            ru=status_online,
            en=(
                "**Online**\n{description}\nVersion **{version_name}**\n"
                "Players: **{players_online}/{players_max}**\n{players_list}\n"
            ),
            version_name=response['version'],
            players_online=response['players']['online'],
            players_max=response['players']['max'],
            players_list='\n'.join(
                f"- [{player}](https://crafty.gg/players/{player})"
                for player in response['players'].get('list', [])
            ),
            description=response['motd']['clean'][0],
        )
    return localized(
        locale,
        ru=minecaft_server_info,
        en=(
            "Join our Minecraft server!\n\n"
            "Java server address: `{server_url}`\n\n"
            "There are only three rules:\n"
            "**1.** Follow the laws of the Russian Federation (do not kill, steal, incite hatred, etc.)\n"
            "**2.** Do not use software or mods that give you an advantage.\n"
            "**3.** Do not stress-test the server.\n\n"
            "Server status: {status}\n"
        ),
        server_url=server_url,
        status=status,
    )


async def rus_to_katakana(text):
    url = 'https://nippon.temerov.org/rus_kana.php'
    form_data = aiohttp.FormData()
    form_data.add_field('text', text)
    form_data.add_field('select', 'katakana')
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data) as resp:
            r = (await resp.text()).split('\n')[-7]
            return {
                "katakana": r.lstrip('<P>Результат преобразования:</P><P>').split('</P>')[0].replace('<BR>', '\n'),
                "racism": '\n'.join([line[:-7].split('")\'>')[-1] for line in r.split('<P>')[3][24:].split('<BR>')[:-1]])
            }


# def get_image_dimensions(image_path):
#     # Открываем изображение
#     with Image.open(image_path) as img:
#         # Получаем размеры изображения
#         width, height = img.size
#         return width, height

# def circle_inversion(image_path, output_path, center, radius, version=1, default_color=(0, 0, 0)):
#     # Открываем изображение
#     with Image.open(image_path) as img:
#         img = img.convert("RGB")  # Убедимся, что изображение в режиме RGB
#         width, height = img.size
#         pixels = np.array(img)  # Преобразуем изображение в массив numpy

#         # Создаем пустое изображение для результата
#         inverted_pixels = np.zeros((height, width, 3), dtype=np.uint8)
#         inverted_pixels[:] = default_color  # Заполняем изображение цветом по умолчанию

#         # Центр окружности
#         x0, y0 = center

#         if version == 1:
#             # Версия 1: исходные пиксели → образы
#             for y in range(height):
#                 for x in range(width):
#                     # Вычисляем новые координаты после инверсии
#                     dx = x - x0
#                     dy = y - y0
#                     distance_squared = dx**2 + dy**2

#                     if distance_squared == 0:
#                         # Если пиксель находится в центре, он остается на месте
#                         x_new, y_new = x0, y0
#                     else:
#                         # Применяем формулу инверсии
#                         scale = radius**2 / distance_squared
#                         x_new = int(x0 + dx * scale)
#                         y_new = int(y0 + dy * scale)

#                     # Проверяем, чтобы новые координаты были в пределах изображения
#                     if 0 <= x_new < width and 0 <= y_new < height:
#                         inverted_pixels[y_new, x_new] = pixels[y, x]

#         elif version == 2:
#             # Версия 2: пиксели выходного изображения → прообразы
#             for y_new in range(height):
#                 for x_new in range(width):
#                     # Вычисляем прообраз (x, y) для пикселя (x_new, y_new)
#                     dx = x_new - x0
#                     dy = y_new - y0
#                     distance_squared = dx**2 + dy**2

#                     if distance_squared == 0:
#                         # Если пиксель находится в центре, его прообраз — он сам
#                         x, y = x0, y0
#                     else:
#                         # Применяем формулу инверсии для вычисления прообраза
#                         scale = radius**2 / distance_squared
#                         x = int(x0 + dx * scale)
#                         y = int(y0 + dy * scale)

#                     # Проверяем, чтобы прообраз был в пределах исходного изображения
#                     if 0 <= x < width and 0 <= y < height:
#                         inverted_pixels[y_new, x_new] = pixels[y, x]

#         else:
#             raise ValueError("Неподдерживаемая версия. Используйте 1 или 2.")

#         # Создаем новое изображение из массива пикселей
#         inverted_image = Image.fromarray(inverted_pixels, "RGB")
#         inverted_image.save(output_path)

# # Пример использования
# image_path = 'sandbox/image.jpg'
# output_path = 'sandbox/outputv1.jpg'

# width, height = get_image_dimensions(image_path)

# center = (width // 2, height // 2)  # Центр окружности (x, y)
# radius = int(min(width, height) * 0.2)  # Радиус окружности

# # Выбираем версию (1 или 2)
# version = 1  # Можно изменить на 1 для первой версии

# circle_inversion(image_path, output_path, center, radius, version=version)
# print(f"Инвертированное изображение сохранено в {output_path}")


def circle_inversion_bytes(
    image_bytes: io.BytesIO,
    version: int = 1,
    default_color: Tuple[int, int, int] = (0, 0, 0),
    # center: Union[Tuple[int, int], None] = None,
    radius_percent: float = 0.2,
) -> io.BytesIO:
    """
    Применяет инверсию относительно окружности к изображению.

    Аргументы:
        image_bytes (io.BytesIO): Входное изображение в формате BytesIO.
        version (int): Версия алгоритма (1 или 2). По умолчанию 1.
        default_color (Tuple[int, int, int]): Цвет по умолчанию для пикселей вне изображения. По умолчанию (0, 0, 0).
        # center (Union[Tuple[int, int], None]): Центр окружности. Если None, вычисляется автоматически. По умолчанию None.
        radius_percent (Union[float, None]): Процент радиуса окружности относительно минимального размера изображения. По умолчанию None.

    Возвращает:
        io.BytesIO: Обработанное изображение в формате BytesIO.
    """
    # Открываем изображение
    with Image.open(image_bytes) as img:
        img = img.convert("RGB")  # Убедимся, что изображение в режиме RGB
        width, height = img.size
        pixels = np.array(img)  # Преобразуем изображение в массив numpy

        # Вычисляем центр и радиус, если они не заданы
        center = (width // 2, height // 2)  # Центр изображения
        radius = int(min(width, height) * radius_percent)  # Радиус как 20% от минимального размера

        # Создаем пустое изображение для результата
        inverted_pixels = np.zeros((height, width, 3), dtype=np.uint8)
        inverted_pixels[:] = default_color  # Заполняем изображение цветом по умолчанию

        # Центр окружности
        x0, y0 = center

        if version == 1:
            # Версия 1: исходные пиксели → образы
            for y in range(height):
                for x in range(width):
                    # Вычисляем новые координаты после инверсии
                    dx = x - x0
                    dy = y - y0
                    distance_squared = dx**2 + dy**2

                    if distance_squared == 0:
                        # Если пиксель находится в центре, он остается на месте
                        x_new, y_new = x0, y0
                    else:
                        # Применяем формулу инверсии
                        scale = radius**2 / distance_squared
                        x_new = int(x0 + dx * scale)
                        y_new = int(y0 + dy * scale)

                    # Проверяем, чтобы новые координаты были в пределах изображения
                    if 0 <= x_new < width and 0 <= y_new < height:
                        inverted_pixels[y_new, x_new] = pixels[y, x]

        elif version == 2:
            # Версия 2: пиксели выходного изображения → прообразы
            for y_new in range(height):
                for x_new in range(width):
                    # Вычисляем прообраз (x, y) для пикселя (x_new, y_new)
                    dx = x_new - x0
                    dy = y_new - y0
                    distance_squared = dx**2 + dy**2

                    if distance_squared == 0:
                        # Если пиксель находится в центре, его прообраз — он сам
                        x, y = x0, y0
                    else:
                        # Применяем формулу инверсии для вычисления прообраза
                        scale = radius**2 / distance_squared
                        x = int(x0 + dx * scale)
                        y = int(y0 + dy * scale)

                    # Проверяем, чтобы прообраз был в пределах исходного изображения
                    if 0 <= x < width and 0 <= y < height:
                        inverted_pixels[y_new, x_new] = pixels[y, x]

        else:
            raise ValueError("Неподдерживаемая версия. Используйте 1 или 2.")

        # Сохраняем результат в BytesIO
        output_bytes = io.BytesIO()
        inverted_image = Image.fromarray(inverted_pixels, "RGB")
        inverted_image.save(output_bytes, format="JPEG")
        output_bytes.seek(0)  # Сбрасываем указатель в начало
        return output_bytes


async def invert_picture(photo):
    # photo: bytes | bytearray | io.BytesIO (Telethon download_media(file=bytes) отдаёт bytes)
    if isinstance(photo, (bytes, bytearray)):
        raw = bytes(photo)
    elif hasattr(photo, "getvalue"):
        raw = photo.getvalue()
    else:
        raw = bytes(photo)
    photo_bytes = io.BytesIO(raw)
    photo_bytes.name = "photo.jpg"  # Указываем имя файла (необязательно)

    # CPU-heavy pixel processing must not block Telegram's event loop or chat actions.
    out = await asyncio.to_thread(circle_inversion_bytes, photo_bytes, version=2)
    out.name = "inverted.jpg"
    return out


name_1 = [
    "Бу",
    "Гай",
    "Иль",
    "Рав",
    "Гали",
    "Ти"
]
name_2 = [
    "лат",
    "дар",
    "мир",
    "дус",
    "шан",
    "мур"
]
jackpot = "бек"
dice_nums = [
    "1️⃣",
    "2️⃣",
    "3️⃣",
    "4️⃣",
    "5️⃣",
    "6️⃣"
]
slot_symbols = [
    "🍻",
    "🍒",
    "🍋",
    "7️⃣"
]


def get_turkic_name(roll_1: int, roll_2: int, roll_slot: int, *, locale=RU) -> dict[str, str]:
    name_1_obj = name_1[roll_1]
    name_2_obj = name_2[roll_2]
    jackpot_obj = None
    if roll_slot in [0, 21, 42, 63]:
        jackpot_obj = jackpot
    roll_1_emoji = dice_nums[roll_1]
    roll_2_emoji = dice_nums[roll_2]
    roll_slot_out = slot_symbols[roll_slot % 4] + slot_symbols[(roll_slot >> 2) % 4] + slot_symbols[(roll_slot >> 4)]
    name = f"{name_1_obj}{name_2_obj}{jackpot_obj if jackpot_obj else ''}"
    message_text = localized(
        locale,
        ru=(
            "Кубик 1: {roll_1_emoji} = {name_1_obj}-\n"
            "Кубик 2: {roll_2_emoji} = -{name_2_obj}\n"
            "Слот: {roll_slot_out}{jackpot_suffix}\n\n"
            "Имя: **{name}**"
        ),
        en=(
            "Die 1: {roll_1_emoji} = {name_1_obj}-\n"
            "Die 2: {roll_2_emoji} = -{name_2_obj}\n"
            "Slot: {roll_slot_out}{jackpot_suffix}\n\n"
            "Name: **{name}**"
        ),
        roll_1_emoji=roll_1_emoji,
        name_1_obj=name_1_obj,
        roll_2_emoji=roll_2_emoji,
        name_2_obj=name_2_obj,
        roll_slot_out=roll_slot_out,
        jackpot_suffix=' 🎰 -' + jackpot_obj if jackpot_obj else '',
        name=name,
    )
    share_text = localized(
        locale,
        ru=(
            "У меня выпало тюркское имя {name} ({roll_1_emoji}+{roll_2_emoji}+{roll_slot_out}).\n"
            "Попробуй: t.me/dot_ch_bot?start=turkic_names"
        ),
        en=(
            "I rolled the Turkic name {name} ({roll_1_emoji}+{roll_2_emoji}+{roll_slot_out}).\n"
            "Try it: t.me/dot_ch_bot?start=turkic_names"
        ),
        name=name,
        roll_1_emoji=roll_1_emoji,
        roll_2_emoji=roll_2_emoji,
        roll_slot_out=roll_slot_out,
    )
    share_url = f"https://t.me/share/url?url={quote(share_text)}"
    return {
        "message_text": message_text,
        "share_url": share_url
    }
