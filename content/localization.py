"""English presentation layer for the bot's declarative content tree."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from libs.i18n import RU, normalize_locale


ENGLISH_TEXT = {
    "🌳 Корень": "🌳 Root",
    "👋 Здесь собраны радио, инструменты, игры, файлы и другие разделы бота.": (
        "👋 Radio, tools, games, files and the bot's other sections live here."
    ),
    "⬅️ Назад": "⬅️ Back",
    "📤 Поделиться": "📤 Share",
    "🔄 Обновить": "🔄 Refresh",
    "📻 Радио": "📻 Radio",
    "🎶 В этой секции вы найдете различные радиостанции и музыкальные потоки, доступные для прослушивания в https://t.me/ch_an?livestream": (
        "🎶 This section contains radio stations and music streams available at "
        "https://t.me/ch_an?livestream"
    ),
    "🔗 Перейти к радио": "🔗 Open the radio",
    "🎷 Радио Jazz Москва 89.1 FM": "🎷 Radio Jazz Moscow 89.1 FM",
    (
        "Четыре AI-радиостанции от [Andon Labs](https://andonlabs.com/radio): агенты ведут эфир "
        "круглосуточно (музыка, расписание, потоки через Live365).\n\n"
        "**🔗 Backlink Broadcast** — ведущий Gemini 3.1 Pro Preview; энергичный эфир, "
        "электроника, альтернатива и поп.\n\n"
        "**🧠 Thinking Frequencies** — ведущий Claude Opus 4.7; спокойнее днём: инди, соул, "
        "электроника и эмбиент.\n\n"
        "**🎈 OpenAIR** — ведущий GPT 5.5; разножанровый микс с упором на атмосферу и плейлисты "
        "(в т.ч. «скандинавские» настроения в расписании).\n\n"
        "**⚡ Grok and Roll** — ведущий Grok 4.3; вечерний разговорный формат, истории и запросы слушателей."
    ): (
        "Four AI radio stations by [Andon Labs](https://andonlabs.com/radio): agents broadcast "
        "around the clock, handling the music, schedules and Live365 streams.\n\n"
        "**🔗 Backlink Broadcast** — hosted by Gemini 3.1 Pro Preview; an energetic mix of "
        "electronic, alternative and pop.\n\n"
        "**🧠 Thinking Frequencies** — hosted by Claude Opus 4.7; calmer during the day, with "
        "indie, soul, electronic and ambient music.\n\n"
        "**🎈 OpenAIR** — hosted by GPT 5.5; a cross-genre mix focused on atmosphere and "
        "playlists, including Scandinavian moods in the schedule.\n\n"
        "**⚡ Grok and Roll** — hosted by Grok 4.3; an evening talk format with stories and "
        "listener requests."
    ),
    "🚗 GTA радио": "🚗 GTA radio",
    "🎮 Откройте для себя музыкальный мир серии игр GTA.\nPowered by https://gtaradio.net": (
        "🎮 Explore the music of the GTA series.\nPowered by https://gtaradio.net"
    ),
    "🏜️ Исследуйте разнообразные музыкальные станции из игры GTA San Andreas.": (
        "🏜️ Explore the radio stations of GTA San Andreas."
    ),
    "🌴 Окунитесь в атмосферу 80-х с радиостанциями GTA Vice City.": (
        "🌴 Step into the 1980s with the radio stations of GTA Vice City."
    ),
    "🌉 Откройте для себя музыкальное наследие GTA III с его уникальными радиостанциями.": (
        "🌉 Explore GTA III through its radio stations."
    ),
    "🕊️ Православное Радио": "🕊️ Orthodox Radio",
    "🙏 Подборка православных радиостанций, включающая чтения, молитвы и обучающие программы.": (
        "🙏 A selection of Orthodox radio stations with readings, prayers and educational programmes."
    ),
    "📖 Чтения": "📖 Readings",
    "📘 Радиостанции, вещающие чтения Евангелия и Псалтиря.": (
        "📘 Stations broadcasting readings of the Gospels and the Psalter."
    ),
    "✝️ Евангелие (Синодальный перевод)": "✝️ Gospels (Synodal translation)",
    "✝️ Евангелие (Церковнославянский)": "✝️ Gospels (Church Slavonic)",
    "✝️ Евангелие (Синодальный музыкальный)": "✝️ Gospels (Synodal, with music)",
    "📜 Псалтирь (Церковнославянский)": "📜 Psalter (Church Slavonic)",
    "📜 Псалтирь (Русский)": "📜 Psalter (Russian)",
    "📜 Псалтирь (Русский музыкальный)": "📜 Psalter (Russian, with music)",
    "📚 Добротолюбие": "📚 Philokalia",
    "📘 Жития Святых": "📘 Lives of the Saints",
    "🙏 Азбука Молитвы": "🙏 Prayer Primer",
    "Школа молитвы от портала «Азбука веры»: https://azbyka.ru/1/molitva. Powered by @azprayer": (
        "A school of prayer by the Azbuka Very portal: https://azbyka.ru/1/molitva. Powered by @azprayer"
    ),
    "🔔 Азбука Молитвы": "🔔 Prayer Primer",
    "🎓 Образование": "🎓 Education",
    "🏫 Радиостанции с обучающими программами и беседами на духовные темы.": (
        "🏫 Stations with educational programmes and conversations on spiritual topics."
    ),
    "🌟 Радио Вера": "🌟 Radio Vera",
    "🕊️ Радио Благо": "🕊️ Radio Blago",
    "🌍 Иностранные Радиостанции": "🌍 International Stations",
    "🎙️ Подборка православных радиостанций из-за рубежа, представляющих различные культуры и языки.": (
        "🎙️ Orthodox radio stations from different countries, cultures and languages."
    ),
    "🇺🇸 Ancient Faith (Музыка) - США": "🇺🇸 Ancient Faith (Music) — USA",
    "🇺🇸 Ancient Faith (Беседы) - США": "🇺🇸 Ancient Faith (Talk) — USA",
    "🌙 Ночной эфир": "🌙 Night broadcast",
    (
        "По расписанию в канале включается **ночной режим**: вместо дневного радио идёт отдельный ночной эфир.\n\n"
        "**Время по UTC:** с **18:15** до **03:00** (через полночь по UTC); после трёх часов снова обычное вещание. "
        "В этот промежуток из бота **нельзя переключать** станции — слушайте ночной стрим в "
        "[лайве канала](https://t.me/ch_an?livestream).\n\n"
        "Подробности и заметки — в [посте канала](https://t.me/ch_an/2387)."
    ): (
        "The channel follows a **night schedule**: a separate night broadcast replaces daytime radio.\n\n"
        "**UTC hours:** **18:15–03:00**, crossing midnight. Regular broadcasting returns at 03:00. "
        "Stations **cannot be changed** through the bot during this period; listen to the night stream in "
        "the [channel live](https://t.me/ch_an?livestream).\n\n"
        "Details and notes are in the [channel post](https://t.me/ch_an/2387)."
    ),
    "🛠 Инструменты и генераторы": "🛠 Tools and generators",
    "Инверсия фотографий и видеокружков, языковые генераторы, проверка истинности, погода и поиск по фотографии.": (
        "Circle inversion for photos and video notes, language generators, truth checks, weather and photo search."
    ),
    "💫 Правильная инверсия™️": "💫 Proper Inversion™️",
    (
        "Инвертирует фотографии и видеокружки [по-настоящему](https://ru.wikipedia.org/wiki/Инверсия_%28геометрия%29) "
        "— относительно окружности.\n\n"
        "**Фотографии**\n"
        "В личном чате приложи фотографию к сообщению через кнопку ниже. В группе приложи фотографию к "
        "сообщению с `@dot_ch_bot` или ответь `@dot_ch_bot` на нужную фотографию.\n\n"
        "**Видеокружки**\n"
        "В личном чате просто пришли кружочек; в группе ответь на нужный кружочек сообщением `@dot_ch_bot`."
    ): (
        "Applies an actual [circle inversion](https://en.wikipedia.org/wiki/Inversive_geometry) to photos and "
        "video notes.\n\n"
        "**Photos**\n"
        "In a private chat, attach a photo using the button below. In a group, attach a photo to a message "
        "starting with `@dot_ch_bot`, or reply `@dot_ch_bot` to the photo.\n\n"
        "**Video notes**\n"
        "In a private chat, just send a video note. In a group, reply `@dot_ch_bot` to the video note."
    ),
    "Инвертировать фотографию": "Invert a photo",
    "invert_picture (приложи фотографию к этому сообщению и отправляй)": (
        "invert_picture (attach a photo to this message and send it)"
    ),
    "🌐 Что-то на иностранном": "🌐 Something in another language",
    "🇯🇵 Руссуко-Японсукий пэрэводутику (простите)": (
        "🇯🇵 Russianno-Japanesey Translator (sorry)"
    ),
    (
        "Переводит любой текст с русского на японскую транслитерацию через катакану.\n\n"
        "В личном чате используй кнопку ниже. В группе напиши `@dot_ch_bot текст` или ответь "
        "`@dot_ch_bot` на сообщение, которое нужно перевести.\n\n"
        "Перевод генерируется [вот тут](https://nippon.temerov.org/rus_kana.php). Ещё раз, простите."
    ): (
        "Transliterates Russian text into Japanese katakana.\n\n"
        "In a private chat, use the button below. In a group, send `@dot_ch_bot text` or reply "
        "`@dot_ch_bot` to the message you want to transliterate.\n\n"
        "The result is generated [here](https://nippon.temerov.org/rus_kana.php). Sorry again."
    ),
    "🔡 Перевести текст": "🔡 Transliterate text",
    "🌸 Башкирские хокку": "🌸 Bashkir haiku",
    "Хокку генерируются [вот тут](http://nevmenandr.net/cgi-bin/haiku.html).\n": (
        "The haiku are generated [here](http://nevmenandr.net/cgi-bin/haiku.html).\n"
    ),
    "🌸 Конкурс башкирских хокку": "🌸 Bashkir Haiku Contest",
    "🪆 Тюркские имена": "🪆 Turkic names",
    "Сгенерируй себе тюркское (мужское) имя!\n\nНажми: /start_turkic_name_game": (
        "Generate a Turkic masculine name.\n\nSend: /start_turkic_name_game"
    ),
    "Ответь на любое сообщение фразой `@dot_ch_bot is this true?`. Бот вынесет решение.": (
        "Reply to any message with `@dot_ch_bot is this true?`. The bot will decide."
    ),
    "🌤️ Погода": "🌤️ Weather",
    "🌡️ Отправьте геопозицию в этот чат, чтобы получить погоду для указанного места.": (
        "🌡️ Send a location to this chat to get the weather there."
    ),
    "🔍 Поиск по розыску": "🔍 Wanted-person search",
    (
        "👤 Инструмент для проверки нахождения людей в розыске. Обратите внимание: точность результатов не "
        "гарантируется, и данная система не должна использоваться как единственный источник информации при "
        "принятии важных решений."
    ): (
        "👤 A tool for checking whether people in a photo appear in wanted-person databases. Results are not "
        "guaranteed to be accurate, and this system must not be the sole source for important decisions."
    ),
    "🔍 Проверить фото": "🔍 Check a photo",
    "search_wanted (приложи фотографию к этому сообщению и отправляй)": (
        "search_wanted (attach a photo to this message and send it)"
    ),
    "🎮 Игры": "🎮 Games",
    "Игры в Telegram, Roblox и Игра Василия™️.": "Games in Telegram and Roblox, plus Vasilii's Game™️.",
    "🎲 Игра Василия™️ (post-wallet)": "🎲 Vasilii's Game™️ (post-wallet)",
    (
        "Василий предлагает сыграть в следующую ||уже бесплатную|| игру:\n"
        "- вы пишете /start_free_vasilii_game.\n"
        "- Василий 100 раз подбрасывает кубик 🎲\n"
        "- каждый раз, когда выпадает 4-6, ваш выигрыш удваивается\n"
        "- каждый раз, когда выпадает 1-3, ваш выигрыш уменьшается в 4 раза\n"
        "- ваш начальный выигрыш равен начальной ставке в 1000 вымышленных тугриков\n\n"
        "Чтобы сыграть в ИГРУ ВАСИЛИЯ™️, пришли сюда /start_free_vasilii_game. Пост-валлет версия, без крипты и кредитов 😎.\n"
        "По мотивам [вот этого поста](https://t.me/ch_an/1864)."
    ): (
        "Vasilii offers the following ||now free|| game:\n"
        "- send /start_free_vasilii_game;\n"
        "- Vasilii rolls a die 100 times 🎲;\n"
        "- every 4–6 doubles your winnings;\n"
        "- every 1–3 divides your winnings by four;\n"
        "- your initial winnings equal the opening stake of 1,000 imaginary tugriks.\n\n"
        "Send /start_free_vasilii_game to play VASILII'S GAME™️. The post-wallet edition has no crypto and no "
        "credit 😎.\nBased on [this post](https://t.me/ch_an/1864)."
    ),
    "📱 Телеграм веб-игры": "📱 Telegram web games",
    "Запускаются прямо в Telegram.": "They run directly in Telegram.",
    "Да, я сделал Game of Life в Roblox.\n\nСм. [пост](https://t.me/ch_an/2393).": (
        "Yes, I made Conway's Game of Life in Roblox.\n\nSee the [post](https://t.me/ch_an/2393)."
    ),
    "🎮 Открыть в Roblox": "🎮 Open in Roblox",
    "📦 Другое": "📦 Other",
    "📂 Моя папка": "📂 My folder",
    "📁 Здесь вы найдёте личные файлы, изображения и аудиозаписи, сохранённые мной.": (
        "📁 Personal files, images and audio saved by me."
    ),
    "🚀 Скрипты Shortcuts": "🚀 Shortcuts scripts",
    (
        "🔧 Здесь собраны мои скрипты для программы [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334), "
        "помогающие автоматизировать повседневные задачи."
    ): (
        "🔧 My scripts for [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334), made to automate "
        "everyday tasks."
    ),
    "📆 **Add LeetCode daily problem solving event.shortcut**\n\nДобавляет событие в календарь на сегодняшнюю задачу в LeetCode.": (
        "📆 **Add LeetCode daily problem solving event.shortcut**\n\nAdds a calendar event for today's LeetCode problem."
    ),
    "🏡 **Run YSH Scenario.shortcut**\n\nЗапускает сценарий из Приложения Умного Дома Яндекса. Работает только на Mac.": (
        "🏡 **Run YSH Scenario.shortcut**\n\nRuns a scene from the Yandex Smart Home app. Mac only."
    ),
    "🐷 **Minecraft server online.shortcut**\n\nПоказывает онлайн майнкрафт сервера и (при возможности) никнеймы игроков.": (
        "🐷 **Minecraft server online.shortcut**\n\nShows the Minecraft server status and player names when available."
    ),
    (
        "📶 **Hotspot QR.shortcut**\n\nВключает раздачу интернета на телефоне, и генерирует удобный экран, на котором "
        "есть название+пароль от WiFi сети, а также QR-код для быстрого подключения."
    ): (
        "📶 **Hotspot QR.shortcut**\n\nTurns on the phone's hotspot and displays its Wi-Fi name and password, plus "
        "a QR code for quick connection."
    ),
    "🎲 **Vasilii Game.shortcut**\n\nКлон хеш-игры Василия (@vas100bot), написанный в Shortcuts.": (
        "🎲 **Vasilii Game.shortcut**\n\nA clone of Vasilii's hash game (@vas100bot), written in Shortcuts."
    ),
    (
        "🧮 **Calculate text.shortcut**\n\nВычисляет выражение из текстовой строки. Работает круче стандартного "
        "калькулятора, например, подсчитает sin(20)^2+cos(20)^2."
    ): (
        "🧮 **Calculate text.shortcut**\n\nEvaluates an expression in a text string. It handles cases such as "
        "sin(20)^2+cos(20)^2 that the standard calculator does not."
    ),
    "🗜 Сжать Фото.shortcut": "🗜 Compress Photos.shortcut",
    (
        "🗜 **Сжать Фото.shortcut**\n\nКонвертирует множество фото по фильтру в HEIF, сохраняет оригинальные "
        "метаданные и время создания.\nПо мотивам https://t.me/ch_an/2289"
    ): (
        "🗜 **Compress Photos.shortcut**\n\nConverts filtered batches of photos to HEIF while preserving their original "
        "metadata and creation dates.\nBased on https://t.me/ch_an/2289"
    ),
    "😊 Папка для стикерпаков и эмодзипаков": "😊 Sticker and emoji pack folder",
    "🍏 Старые иконки приложений  Apple": "🍏 Old  Apple app icons",
    "SF7 эмодзипаки": "SF7 emoji packs",
    "Другое": "Other",
    "📄 Хорошие новости №11.pdf": "📄 Good News No. 11.pdf",
    "📦 Presentation защита ВКР.zip": "📦 Graduation thesis presentation.zip",
    "**📦 Presentation защита ВКР.zip**": "**📦 Graduation thesis presentation.zip**",
    "🔗 Ссылки на меня": "🔗 Links to me",
    "👤 Здесь вы найдете ссылки на меня.": "👤 Links to my work and profiles.",
    "📢 Telegram-канал": "📢 Telegram channel",
    "💬 Группа канала": "💬 Channel group",
    "🤖 Telegram-бот (этот самый)": "🤖 Telegram bot (this one)",
    "😎 Веб-сайт": "😎 Website",
    "⌨️ Исходный код · AGPL-3.0": "⌨️ Source code · AGPL-3.0",
    "Мои данные": "My data",
    (
        "<b>Центр управления данными</b>\n\nЗдесь можно проверить постоянные хранилища приложения, получить полную "
        "выгрузку или безвозвратно удалить всё, что бот хранит о вас.\n\nОперации относятся только к данным самого "
        "приложения, не к истории чата в Telegram."
    ): (
        "<b>Data centre</b>\n\nInspect the application's persistent storage, get a complete export or permanently "
        "delete everything the bot stores about you.\n\nThese operations cover only the application's own data, not your "
        "Telegram chat history."
    ),
    "🔎 Провести аудит": "🔎 Run audit",
    "↩️ В центр данных": "↩️ Back to data centre",
    "📋 Скопировать итог": "📋 Copy summary",
    "@dot_ch_bot · найдено 0 · удалено 0 · хранится 0 Б": (
        "@dot_ch_bot · found 0 · deleted 0 · stored 0 B"
    ),
    "🗑 Удалить": "🗑 Delete",
    "🗑 Удалить безвозвратно": "🗑 Delete permanently",
    "↻ Повторить": "↻ Try again",
    "📦 Получить takeout": "📦 Get takeout",
    "🗑 Удалить всё": "🗑 Delete everything",
    "🔒 NDA папка": "🔒 NDA folder",
    "👀 Если вы её видите, то вам это разрешили.": "👀 If you can see it, you were given access.",
    "㊙️ Клика": "㊙️ Clique",
    "🤫 Дело": "🤫 The Case",
    "См. [пост](https://t.me/ch_an/1884).": "See the [post](https://t.me/ch_an/1884).",
    "🎧 Перейти к ДЕЛУ": "🎧 Open THE CASE",
    "⛏️ Анатолий Ч. | minecraft-сервер": "⛏️ Anatolii Ch. | Minecraft server",
    "🗺️ Карта сервера": "🗺️ Server map",
    "🔑 Вход на сервер": "🔑 Server login",
    "💬 Чат сервера": "💬 Server chat",
    "🎙️ Голосовой чат сервера": "🎙️ Server voice chat",
    "🌐 Язык бота": "🌐 Bot language",
    (
        "Бот выбирает язык по языку интерфейса Telegram. Если Telegram на русском, бот отвечает по-русски; "
        "для всех остальных языков используется английский.\n\nЧтобы изменить язык: **Telegram → Настройки → Язык**. "
        "После изменения заново откройте меню или отправьте /start."
    ): (
        "The bot follows Telegram's interface language. If Telegram is set to Russian, the bot replies in Russian; "
        "every other language uses English.\n\nTo change it, open **Telegram → Settings → Language**. After changing "
        "the language, reopen the menu or send /start."
    ),
}


_SF7_DESCRIPTION = re.compile(
    r"^(?P<packs>\d+) эмодзипаков SF7: (?P<weights>\d+) толщин × (?P<groups>\d+) групп\.$"
)


def _english_text(value: str) -> str:
    translated = ENGLISH_TEXT.get(value)
    if translated is not None:
        return translated
    sf7_match = _SF7_DESCRIPTION.fullmatch(value)
    if sf7_match:
        return (
            f"{sf7_match['packs']} SF7 emoji packs: "
            f"{sf7_match['weights']} weights × {sf7_match['groups']} groups."
        )
    return value


def _translate_value(value: Any) -> Any:
    if isinstance(value, str):
        return _english_text(value)
    if isinstance(value, dict):
        return {key: _translate_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_translate_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_translate_value(item) for item in value)
    return value


def localize_content_tree(tree: dict[str, Any], locale: str) -> dict[str, Any]:
    """Return an isolated tree localized without changing route identifiers."""

    if normalize_locale(locale) == RU:
        return deepcopy(tree)
    return _translate_value(tree)
