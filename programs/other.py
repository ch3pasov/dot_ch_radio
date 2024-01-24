import aiohttp
from volume.config.minecraft_config import server_url, bedrock_proxy_url
import re


async def aiohttp_get(url, type='text'):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url) as resp:
            match type:
                case 'text':
                    return await resp.text()
                case 'json':
                    return await resp.json()
                case _:
                    raise ValueError("Unknown type")


async def get_bashkir_haiku():
    return "\n".join(
        (await aiohttp_get('http://nevmenandr.net/cgi-bin/haiku.html', 'text')).split("\n")[119:122]
    ).replace("</span></td></tr>", "").replace('<tr><td></td><td><span style="color: #363636; font: normal 1.8em/1.36 Georgia">', "")


async def get_weather(location):
    lat = location.latitude
    lon = location.longitude
    weather_data = await aiohttp_get(f'https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&units=metric&lang=ru&appid=OPENWEATHER_API_KEY_REMOVED', 'json')

    temperature = weather_data['main']['temp']
    temperature_feels = weather_data['main']['feels_like']
    wind_speed = weather_data['wind']['speed']

    return f"В {weather_data['name']} {str(temperature)}℃\nОщущается как {temperature_feels}℃\nСкорость ветра {wind_speed}м/с"


minecaft_server_info = """Присоединяйтесь к нашему Minecraft серверу!

Адрес java-сервера: `{server_url}`
Прокси для bedrock: `{bedrock_proxy_url}`

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


async def get_minecraft_server_info():
    response = await aiohttp_get(f'https://api.mcsrvstat.us/2/{server_url}', 'json')
    if not response['online']:
        status = status_offline
    else:
        status = status_online.format(
            version_name=response['version'],
            players_online=response['players']['online'],
            players_max=response['players']['max'],
            players_list='\n'.join([f"- [{player}](https://crafty.gg/players/{player})" for player in response['players']['list']]) if 'list' in response['players'] else '',
            description=response['motd']['clean'][0]
        )
    return minecaft_server_info.format(
        server_url=server_url,
        bedrock_proxy_url=bedrock_proxy_url,
        status=status
    )


nadezhdin_regex = r'                                <span class="progressbar__el__text">Собрано подписей: (\d+)( / 2500)?</span>'
out = '''
Считаю количество подписей с nadezhdin2024.ru/addresses, потому что либералы не умеют.

Всего собрано подписей: **{scores_all:,}**.
С ограниченим в 2500 на регион подписей: **{scores_2500:,}**.
Среди этих подписей нужно **100,000** идеально заполненных подписей. Сколько их сейчас — неизвестно.
'''


async def get_nadezhdin():
    text = await aiohttp_get('https://nadezhdin2024.ru/addresses', 'text')
    scores_raw = [int(region_score[0]) for region_score in re.findall(nadezhdin_regex, text)]
    scores_all = sum(scores_raw)
    scores_2500 = sum([min(2500, score) for score in scores_raw])
    return out.format(scores_all=scores_all, scores_2500=scores_2500)
