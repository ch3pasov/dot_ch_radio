import json
from functools import lru_cache
from html import escape
from pathlib import Path

from content.localization import localize_content_tree
from libs.content_schema import folder, normalize_tree
from libs.i18n import EN, RU, localized, normalize_locale


EMOJI_PACK_LINKS_PATH = Path(__file__).resolve().parent.parent / "config" / "emoji_pack_links.json"
SF7_CUSTOM_EMOJI_INDEX_PATH = Path(__file__).resolve().parent / "sf7-custom-emoji-index.json"
SF7_WEIGHT_ORDER = [
    "Ultralight",
    "Thin",
    "Light",
    "Regular",
    "Medium",
    "Semibold",
    "Bold",
    "Heavy",
    "Black",
]
SF7_WEIGHT_ICON_SYMBOL = "tray.full"
SF7_GROUP_CATEGORIES = [
    (
        "symbols_numbers",
        "Symbols & Numbers",
        {
            "arrows_bidirectional",
            "arrows_down",
            "arrows_general",
            "arrows_left_01",
            "arrows_left_02",
            "arrows_right",
            "arrows_turning_01",
            "arrows_turning_02",
            "arrows_up",
            "charts_data",
            "math_controls",
            "math_minus",
            "math_plus",
            "media_controls",
            "number_0",
            "number_1",
            "number_10",
            "number_2",
            "number_3",
            "number_4",
            "number_5",
            "number_6",
            "number_7",
            "number_8",
            "number_9",
            "numbers_general",
            "status_alerts",
            "status_close_remove",
            "status_general",
            "status_questions",
            "status_success",
            "status_warnings",
            "text_symbols",
            "unmapped_001",
            "unmapped_002",
            "unmapped_003",
            "unmapped_004",
            "unmapped_005",
            "unmapped_006",
            "unmapped_007",
            "unmapped_008",
            "unmapped_009",
            "unmapped_010",
            "unmapped_011",
            "unmapped_012",
        },
    ),
    (
        "life_places",
        "Life & Places",
        {
            "body",
            "calendar",
            "celebration",
            "food_drink",
            "games_awards",
            "health_medical",
            "human_activity",
            "maps_navigation",
            "nature",
            "people_01",
            "people_02",
            "people_03",
            "places_home_01",
            "places_home_02",
            "shopping",
            "sports",
            "time",
            "transport_air_water",
            "transport_bicycles",
            "transport_cars",
            "transport_fuel_charging",
            "transport_general",
            "transport_public",
            "weather",
        },
    ),
    (
        "devices_objects",
        "Devices & Objects",
        {
            "audio_devices",
            "audio_media",
            "camera_video",
            "commerce_money_01",
            "commerce_money_02",
            "communication",
            "computers_peripherals",
            "connectivity_power",
            "devices_general",
            "documents_storage",
            "education_docs",
            "misc",
            "phones_tablets",
            "screens_tv",
            "search_light",
            "security",
            "tools",
            "watches",
            "writing_drawing",
        },
    ),
]
SF7_GROUP_ICON_SYMBOL_OVERRIDES = {
    "people_01": "figure",
    "people_02": "figure.run",
    "people_03": "person.2",
}


def _button_icon(icon_id):
    return {"button_icon": icon_id} if icon_id else {}


@lru_cache(maxsize=1)
def _sf7_symbols():
    with SF7_CUSTOM_EMOJI_INDEX_PATH.open(encoding="utf-8") as index_file:
        return json.load(index_file)["symbols"]


def sf7_button_icon(symbol_name, weight="Regular"):
    """Return a Telegram button icon by its SF7 symbol name, with safe fallback."""

    return _button_icon(_sf7_custom_emoji_id(_sf7_symbols(), symbol_name, weight))


def sf7_title_icon(symbol_name, weight="Regular"):
    """Return a Telegram message-title icon by its SF7 symbol name."""

    icon_id = _sf7_custom_emoji_id(_sf7_symbols(), symbol_name, weight)
    return {"title_icon": icon_id} if icon_id else {}


def _custom_emoji_html(icon_id, fallback_emoji):
    return f'<tg-emoji emoji-id="{icon_id}">{escape(fallback_emoji)}</tg-emoji> ' if icon_id else ""


def _sf7_custom_emoji_id(symbols, symbol_name, weight):
    symbol = symbols.get(symbol_name)
    if not symbol:
        return None
    weighted_icon = symbol.get("weights", {}).get(weight) or symbol.get("weights", {}).get("Regular")
    if not weighted_icon:
        return None
    return weighted_icon.get("custom_emoji_id")


def _sf7_group_icon_symbols(symbols):
    group_icons = dict(SF7_GROUP_ICON_SYMBOL_OVERRIDES)
    for symbol_name, symbol in symbols.items():
        group_id = symbol.get("group_id")
        if group_id and group_id not in group_icons:
            group_icons[group_id] = symbol_name
    return group_icons


def _weight_name(weight_slug):
    normalized_slug = weight_slug.lower()
    for weight in SF7_WEIGHT_ORDER:
        if weight.lower() == normalized_slug:
            return weight
    return None


def _sf7_search_line(symbol_name, symbol, weight):
    weighted_icon = symbol.get("weights", {}).get(weight)
    if not weighted_icon:
        return None
    icon_id = weighted_icon.get("custom_emoji_id")
    fallback_emoji = symbol.get("primary_emoji") or "🔹"
    return f"{_custom_emoji_html(icon_id, fallback_emoji)}<code>{escape(symbol_name)}</code>"


def search_sf7_custom_emoji_html(weight_slug, query, limit=40, *, locale=RU):
    weight = _weight_name(weight_slug)
    if weight is None:
        return None

    normalized_query = query.strip().lower()
    if len(normalized_query) < 2:
        return localized(
            locale,
            ru=(
                f"<b>{escape(weight)}</b>\n"
                f"Напиши запрос подлиннее: <code>/sf7_search_{weight.lower()} tray</code>"
            ),
            en=(
                f"<b>{escape(weight)}</b>\n"
                f"Use a longer query: <code>/sf7_search_{weight.lower()} tray</code>"
            ),
        )

    symbols = _sf7_symbols()

    matches = []
    for symbol_name, symbol in symbols.items():
        searchable = " ".join(
            [
                symbol_name,
                symbol.get("group_id", ""),
                symbol.get("group_title", ""),
                " ".join(symbol.get("categories", [])),
            ]
        ).lower()
        if normalized_query in searchable:
            line = _sf7_search_line(symbol_name, symbol, weight)
            if line:
                matches.append(line)
        if len(matches) >= limit:
            break

    if not matches:
        return localized(
            locale,
            ru=(
                f"<b>{escape(weight)}</b>\n"
                f"По запросу <code>{escape(query.strip())}</code> ничего не нашлось."
            ),
            en=(
                f"<b>{escape(weight)}</b>\n"
                f"Nothing found for <code>{escape(query.strip())}</code>."
            ),
        )

    return localized(
        locale,
        ru=(
            f"<b>{escape(weight)}</b>\n"
            f"{len(matches)} результатов по <code>{escape(query.strip())}</code>\n\n"
            + "\n".join(matches)
        ),
        en=(
            f"<b>{escape(weight)}</b>\n"
            f"{len(matches)} results for <code>{escape(query.strip())}</code>\n\n"
            + "\n".join(matches)
        ),
    )


def _build_sf7_emoji_pack_tree():
    with EMOJI_PACK_LINKS_PATH.open(encoding="utf-8") as links_file:
        links_config = json.load(links_file)

    weights = [weight for weight in SF7_WEIGHT_ORDER if weight in links_config["weights"]]
    url_template = links_config["url_template"]
    set_name_template = links_config["set_name_template"]
    symbols = _sf7_symbols()
    group_icon_symbols = _sf7_group_icon_symbols(symbols)

    groups = {}
    for pack in links_config["packs"]:
        groups.setdefault(
            pack["group_id"],
            {
                "title": pack["title"],
                "count": pack["count"],
            },
        )

    if len(groups) != links_config["groups_count"]:
        raise ValueError(f"Expected {links_config['groups_count']} emoji groups, got {len(groups)}")

    def pack_url(weight, group_id):
        set_name = set_name_template.format(weight_slug=weight.lower(), group_slug=group_id)
        return url_template.format(set_name=set_name)

    def group_icon(group_id, weight):
        return _sf7_custom_emoji_id(symbols, group_icon_symbols.get(group_id), weight)

    def group_fallback_emoji(group_id):
        symbol = symbols.get(group_icon_symbols.get(group_id), {})
        return symbol.get("primary_emoji") or "🔹"

    def weight_icon(weight):
        return _sf7_custom_emoji_id(symbols, SF7_WEIGHT_ICON_SYMBOL, weight)

    def group_link_lines(weight, group_items):
        return "\n".join(
            (
                f"{_custom_emoji_html(group_icon(group_id, weight), group_fallback_emoji(group_id))}"
                f'<a href="{escape(pack_url(weight, group_id), quote=True)}">'
                f"{escape(group['title'])} ({group['count']})"
                "</a>"
            )
            for group_id, group in group_items
        )

    def group_pages(weight):
        group_items = list(groups.items())
        categorized_group_ids = set()
        pages = []
        for category_id, category_title, category_group_ids in SF7_GROUP_CATEGORIES:
            page_items = [(group_id, group) for group_id, group in group_items if group_id in category_group_ids]
            categorized_group_ids.update(group_id for group_id, _ in page_items)
            if not page_items:
                continue
            pages.append(
                folder(
                    category_title,
                    id=category_id,
                    description=group_link_lines(weight, page_items),
                    parse_mode="html",
                    disable_web_page_preview=1,
                    **_button_icon(group_icon(page_items[0][0], weight)),
                )
            )
        uncategorized_items = [(group_id, group) for group_id, group in group_items if group_id not in categorized_group_ids]
        if uncategorized_items:
            pages.append(
                folder(
                    "Other",
                    id="other",
                    description=group_link_lines(weight, uncategorized_items),
                    parse_mode="html",
                    disable_web_page_preview=1,
                    **_button_icon(group_icon(uncategorized_items[0][0], weight)),
                )
            )
        return pages

    return folder(
        "SF7 эмодзипаки",
        aliases=["sf7_emojis"],
        description=(
            f"{links_config['packs_count']} эмодзипаков SF7: "
            f"{len(weights)} толщин × {len(groups)} групп."
        ),
        children_columns=1,
        **_button_icon(_sf7_custom_emoji_id(symbols, "square.grid.2x2", "Regular")),
        children=[
            folder(
                weight,
                id=weight.lower(),
                children_columns=1,
                **_button_icon(weight_icon(weight)),
                children=[
                    folder(
                        "Search",
                        id="search",
                        button_style="primary",
                        switch_inline_query_current_chat=f"/sf7_search_{weight.lower()} ",
                        **_button_icon(_sf7_custom_emoji_id(symbols, "magnifyingglass", weight)),
                    ),
                    *group_pages(weight),
                ],
            )
            for weight in weights
        ],
    )


common_tree = {
    "name": "🌳 Корень",
    "description": "👋 Здесь собраны радио, инструменты, игры, файлы и другие разделы бота.",
    "aliases": ["root"],
    "navigation_ui": {
        "back": {
            "text": "⬅️ Назад",
            **sf7_button_icon("chevron.left"),
        },
        "share": {
            "text": "📤 Поделиться",
            **sf7_button_icon("square.and.arrow.up"),
        },
        "refresh": {
            "text": "🔄 Обновить",
            **sf7_button_icon("arrow.clockwise"),
        },
    },
    "children": {
        "radio": {
            "name": "📻 Радио",
            "description": "🎶 В этой секции вы найдете различные радиостанции и музыкальные потоки, доступные для прослушивания в https://t.me/ch_an?livestream",
            "aliases": ["radio"],
            "custom": "radio_now_playing",
            "refresh": 1,
            **sf7_button_icon("radio"),
            "children": {
                "go_to_radio": {
                    "name": "🔗 Перейти к радио",
                    "url": "https://t.me/ch_an?livestream",
                    "button_style": "success",
                    **sf7_button_icon("play.fill"),
                },
                "lofi_girl": {
                    "name": "🎧 LoFi Girl",
                    "radio_url": "https://live.lofiradio.ru/lofi_mp3_128",
                },
                "radio_jazz": {
                    "name": "🎷 Радио Jazz Москва 89.1 FM",
                    "radio_url": "https://nashe1.hostingradio.ru/jazz-256",
                },
                "andon_fm": {
                    "name": "🤖 Andon FM",
                    "aliases": ["andon_fm"],
                    "description": (
                        "Четыре AI-радиостанции от [Andon Labs](https://andonlabs.com/radio): агенты ведут эфир "
                        "круглосуточно (музыка, расписание, потоки через Live365).\n\n"
                        "**🔗 Backlink Broadcast** — ведущий Gemini 3.1 Pro Preview; энергичный эфир, "
                        "электроника, альтернатива и поп.\n\n"
                        "**🧠 Thinking Frequencies** — ведущий Claude Opus 4.7; спокойнее днём: инди, соул, "
                        "электроника и эмбиент.\n\n"
                        "**🎈 OpenAIR** — ведущий GPT 5.5; разножанровый микс с упором на атмосферу и плейлисты "
                        "(в т.ч. «скандинавские» настроения в расписании).\n\n"
                        "**⚡ Grok and Roll** — ведущий Grok 4.3; вечерний разговорный формат, истории и запросы слушателей."
                    ),
                    "children": {
                        "andon_backlink": {
                            "name": "🔗 Backlink Broadcast",
                            "radio_url": "https://streaming.live365.com/a13541"
                        },
                        "andon_thinking": {
                            "name": "🧠 Thinking Frequencies",
                            "radio_url": "https://streaming.live365.com/a46431"
                        },
                        "andon_openair": {
                            "name": "🎈 OpenAIR",
                            "radio_url": "https://streaming.live365.com/a81044"
                        },
                        "andon_grok_roll": {
                            "name": "⚡ Grok and Roll",
                            "radio_url": "https://streaming.live365.com/a15419"
                        },
                    },
                },
                "gta": {
                    "name": "🚗 GTA радио",
                    "description": "🎮 Откройте для себя музыкальный мир серии игр GTA.\nPowered by https://gtaradio.net",
                    "children": {
                        "sa": {
                            "name": "🌆 GTA San Andreas",
                            "description": "🏜️ Исследуйте разнообразные музыкальные станции из игры GTA San Andreas.",
                            "children": {
                                "bounce-fm": {
                                    "name": "🎶 Bounce FM",
                                    "radio_url": "https://audio.gtaradio.net/sa/bounce-fm"
                                },
                                "csr": {
                                    "name": "🎵 CSR 103.9",
                                    "radio_url": "https://audio.gtaradio.net/sa/csr"
                                },
                                "k-dst": {
                                    "name": "🤠 K-DST",
                                    "radio_url": "https://audio.gtaradio.net/sa/k-dst"
                                },
                                "k-jah": {
                                    "name": "🔥 K-JAH West",
                                    "radio_url": "https://audio.gtaradio.net/sa/k-jah"
                                },
                                "k-rose": {
                                    "name": "🌹 K-Rose",
                                    "radio_url": "https://audio.gtaradio.net/sa/k-rose"
                                },
                                "master-sounds": {
                                    "name": "💿 Master Sounds 98.3",
                                    "radio_url": "https://audio.gtaradio.net/sa/master-sounds"
                                },
                                "playback-fm": {
                                    "name": "⏪ Playback FM",
                                    "radio_url": "https://audio.gtaradio.net/sa/playback-fm"
                                },
                                "radio-los-santos": {
                                    "name": "🏙️ Radio Los Santos",
                                    "radio_url": "https://audio.gtaradio.net/sa/radio-los-santos"
                                },
                                "radio-x": {
                                    "name": "🤘 Radio X",
                                    "radio_url": "https://audio.gtaradio.net/sa/radio-x"
                                },
                                "sfur": {
                                    "name": "🎧 SF-UR",
                                    "radio_url": "https://audio.gtaradio.net/sa/sfur"
                                },
                                "wctr": {
                                    "name": "📢 WCTR",
                                    "radio_url": "https://audio.gtaradio.net/sa/wctr"
                                }
                            }
                        },
                        "vc": {
                            "name": "🏝️ GTA Vice City",
                            "description": "🌴 Окунитесь в атмосферу 80-х с радиостанциями GTA Vice City.",
                            "children": {
                                "emotion": {
                                    "name": "💖 Emotion 98.3",
                                    "radio_url": "https://audio.gtaradio.net/vc/emotion"
                                },
                                "espant": {
                                    "name": "🎷 Espantoso",
                                    "radio_url": "https://audio.gtaradio.net/vc/espant"
                                },
                                "fever": {
                                    "name": "🔥 Fever 105",
                                    "radio_url": "https://audio.gtaradio.net/vc/fever"
                                },
                                "flash": {
                                    "name": "⚡ Flash FM",
                                    "radio_url": "https://audio.gtaradio.net/vc/flash"
                                },
                                "kchat": {
                                    "name": "💬 K-Chat",
                                    "radio_url": "https://audio.gtaradio.net/vc/kchat"
                                },
                                "vcpr": {
                                    "name": "🎙️ VCPR",
                                    "radio_url": "https://audio.gtaradio.net/vc/vcpr"
                                },
                                "vrock": {
                                    "name": "🎸 V-Rock",
                                    "radio_url": "https://audio.gtaradio.net/vc/vrock"
                                },
                                "wave": {
                                    "name": "🌊 Wave 103",
                                    "radio_url": "https://audio.gtaradio.net/vc/wave"
                                },
                                "wild": {
                                    "name": "🐅 Wildstyle",
                                    "radio_url": "https://audio.gtaradio.net/vc/wild"
                                }
                            }
                        },
                        "3": {
                            "name": "🌃 GTA III",
                            "description": "🌉 Откройте для себя музыкальное наследие GTA III с его уникальными радиостанциями.",
                            "children": {
                                "head": {
                                    "name": "🎧 Head Radio",
                                    "radio_url": "https://audio.gtaradio.net/3/head"
                                },
                                "class": {
                                    "name": "🎻 Double Clef FM",
                                    "radio_url": "https://audio.gtaradio.net/3/class"
                                },
                                "kjah": {
                                    "name": "🌴 K-JAH",
                                    "radio_url": "https://audio.gtaradio.net/3/kjah"
                                },
                                "rise": {
                                    "name": "🔝 Rise FM",
                                    "radio_url": "https://audio.gtaradio.net/3/rise"
                                },
                                "lips": {
                                    "name": "💋 Lips 106",
                                    "radio_url": "https://audio.gtaradio.net/3/lips"
                                },
                                "game": {
                                    "name": "🕹️ Game FM",
                                    "radio_url": "https://audio.gtaradio.net/3/game"
                                },
                                "msx": {
                                    "name": "🎚️ MSX FM",
                                    "radio_url": "https://audio.gtaradio.net/3/msx"
                                },
                                "flash": {
                                    "name": "⚡ Flashback 95.6",
                                    "radio_url": "https://audio.gtaradio.net/3/flash"
                                },
                                "chat": {
                                    "name": "💬 Chatterbox FM",
                                    "radio_url": "https://audio.gtaradio.net/3/chat"
                                }
                            }
                        }
                    }
                },
                "orthodox_radio": {
                    "name": "🕊️ Православное Радио",
                    "description": "🙏 Подборка православных радиостанций, включающая чтения, молитвы и обучающие программы.",
                    "children": {
                        "readings": {
                            "name": "📖 Чтения",
                            "description": "📘 Радиостанции, вещающие чтения Евангелия и Псалтиря.",
                            "children": {
                                "evangelie_sinod": {
                                    "name": "✝️ Евангелие (Синодальный перевод)",
                                    "radio_url": "https://radio.azbyka.ru/evangelie"
                                },
                                "evangelie-csya": {
                                    "name": "✝️ Евангелие (Церковнославянский)",
                                    "radio_url": "https://radio.azbyka.ru/chitaem-evangelie-csya"
                                },
                                "evangelie-sinod-muz": {
                                    "name": "✝️ Евангелие (Синодальный музыкальный)",
                                    "radio_url": "https://radio.azbyka.ru/chitaem-evangelie-sinod-muz"
                                },
                                "psaltir_csya": {
                                    "name": "📜 Псалтирь (Церковнославянский)",
                                    "radio_url": "https://radio.azbyka.ru/psaltir"
                                },
                                "psaltir-rus": {
                                    "name": "📜 Псалтирь (Русский)",
                                    "radio_url": "https://radio.azbyka.ru/psaltir-rus"
                                },
                                "psaltir-rus-muz": {
                                    "name": "📜 Псалтирь (Русский музыкальный)",
                                    "radio_url": "https://radio.azbyka.ru/psaltir-rus-muz"
                                },
                                "dorbrotolubie": {
                                    "name": "📚 Добротолюбие",
                                    "radio_url": "https://radio.azbyka.ru/dobrotolubie"
                                },
                                "lives": {
                                    "name": "📘 Жития Святых",
                                    "radio_url": "https://radio.azbyka.ru/lives"
                                },
                            }
                        },
                        "prayers": {
                            "name": "🙏 Азбука Молитвы",
                            "description": "Школа молитвы от портала «Азбука веры»: https://azbyka.ru/1/molitva. Powered by @azprayer",
                            "children": {
                                "azbyka-molitvy": {
                                    "name": "🔔 Азбука Молитвы",
                                    "radio_url": "https://radio.azbyka.ru/azbyka-molitvy"
                                }
                            }
                        },
                        "education": {
                            "name": "🎓 Образование",
                            "description": "🏫 Радиостанции с обучающими программами и беседами на духовные темы.",
                            "children": {
                                "vera": {
                                    "name": "🌟 Радио Вера",
                                    "radio_url": "https://radiovera.hostingradio.ru:8007/radiovera_128"
                                },
                                "blago": {
                                    "name": "🕊️ Радио Благо",
                                    "radio_url": "https://live.radioblago.ru/live-1.mp3"
                                }
                            }
                        },
                        "foreigns": {
                            "name": "🌍 Иностранные Радиостанции",
                            "description": "🎙️ Подборка православных радиостанций из-за рубежа, представляющих различные культуры и языки.",
                            "children": {
                                "ancient-faith-music": {
                                    "name": "🇺🇸 Ancient Faith (Музыка) - США",
                                    "radio_url": "https://ancientfaith.streamguys1.com/music"
                                },
                                "ancient-faith-talk": {
                                    "name": "🇺🇸 Ancient Faith (Беседы) - США",
                                    "radio_url": "https://ancientfaith.streamguys1.com/talk"
                                }
                            }
                        }
                    }
                },
                "night_radio": {
                    "name": "🌙 Ночной эфир",
                    "aliases": ["night_radio"],
                    "description": (
                        "По расписанию в канале включается **ночной режим**: вместо дневного радио идёт "
                        "отдельный ночной эфир.\n\n"
                        "**Время по UTC:** с **18:15** до **03:00** (через полночь по UTC); после трёх часов снова "
                        "обычное вещание. В этот промежуток из бота **нельзя переключать** станции — слушайте "
                        "ночной стрим в [лайве канала](https://t.me/ch_an?livestream).\n\n"
                        "Подробности и заметки — в [посте канала](https://t.me/ch_an/2387)."
                    ),
                }
            }
        },
        "tools": {
            "name": "🛠 Инструменты и генераторы",
            "description": (
                "Инверсия фотографий и видеокружков, языковые генераторы, "
                "проверка истинности, погода и поиск по фотографии."
            ),
            "aliases": ["tools"],
            **sf7_button_icon("wrench.and.screwdriver"),
            "children": {
                "invert_picture": {
                    "name": "💫 Правильная инверсия™️",
                    "description": (
                        "Инвертирует фотографии и видеокружки "
                        "[по-настоящему](https://ru.wikipedia.org/wiki/Инверсия_%28геометрия%29) — "
                        "относительно окружности.\n\n"
                        "**Фотографии**\n"
                        "В личном чате приложи фотографию к сообщению через кнопку ниже. "
                        "В группе приложи фотографию к сообщению с `@dot_ch_bot` "
                        "или ответь `@dot_ch_bot` на нужную фотографию.\n\n"
                        "**Видеокружки**\n"
                        "В личном чате просто пришли кружочек; в группе ответь "
                        "на нужный кружочек сообщением `@dot_ch_bot`."
                    ),
                    "telegram_file_id": 'BQADAgAD7pwAAm8JmUmhLedYHQzukAI',
                    "aliases": ["inversion", "invert_picture"],
                    "children": {
                        "invert_picture_command": {
                            "name": "Инвертировать фотографию",
                            "switch_inline_query_current_chat": "invert_picture (приложи фотографию к этому сообщению и отправляй)",
                            "button_style": "primary",
                            **sf7_button_icon("photo"),
                        }
                    },
                },
                "foreign_languages": {
                    "name": "🌐 Что-то на иностранном",
                    **sf7_button_icon("globe"),
                    "children": {
                        "katakana_racism": {
                            "name": "🇯🇵 Руссуко-Японсукий пэрэводутику (простите)",
                            "description": (
                                "Переводит любой текст с русского на японскую транслитерацию через катакану.\n\n"
                                "В личном чате используй кнопку ниже. В группе напиши "
                                "`@dot_ch_bot текст` или ответь `@dot_ch_bot` на сообщение, "
                                "которое нужно перевести.\n\n"
                                "Перевод генерируется [вот тут](https://nippon.temerov.org/rus_kana.php). "
                                "Ещё раз, простите."
                            ),
                            "telegram_file_id": 'BQADAgAD7ZwAAm8JmUnXVfb1QoFRYgI',
                            "aliases": ["rus_to_katakana"],
                            "children": {
                                "rus_to_katakana_command": {
                                    "name": "🔡 Перевести текст",
                                    "switch_inline_query_current_chat": "rus_to_katakana ",
                                    "button_style": "primary",
                                }
                            }
                        },
                        "bashkir_haiku": {
                            "name": "🌸 Башкирские хокку",
                            "description": "Хокку генерируются [вот тут](http://nevmenandr.net/cgi-bin/haiku.html).\n",
                            "custom": "bashkir_haiku",
                            "refresh": 1,
                            "aliases": ["bashkir_haiku"],
                            "children": {
                                "haiku_contest": {
                                    "name": "🌸 Конкурс башкирских хокку",
                                    "url": "https://bashkirhaiku.anatoliy.ch",
                                }
                            }
                        },
                        "turkic_names": {
                            "name": "🪆 Тюркские имена",
                            "description": "Сгенерируй себе тюркское (мужское) имя!\n\nНажми: /start_turkic_name_game",
                            "aliases": ["turkic_names"],
                            "beta_access": 0,
                        },
                    }
                },
                "is_this_true": {
                    "name": "Is this true?",
                    "description": (
                        "Ответь на любое сообщение фразой "
                        "`@dot_ch_bot is this true?`. Бот вынесет решение."
                    ),
                    "aliases": ["is_this_true"],
                    **sf7_button_icon("questionmark.circle"),
                },
                "weather": {
                    "name": "🌤️ Погода",
                    "description": "🌡️ Отправьте геопозицию в этот чат, чтобы получить погоду для указанного места.",
                    "aliases": ["weather"],
                    **sf7_button_icon("cloud.sun"),
                },
                "search_wanted": {
                    "name": "🔍 Поиск по розыску",
                    "description": "👤 Инструмент для проверки нахождения людей в розыске. Обратите внимание: точность результатов не гарантируется, и данная система не должна использоваться как единственный источник информации при принятии важных решений.",
                    "aliases": ["search_wanted"],
                    **sf7_button_icon("magnifyingglass"),
                    "children": {
                        "search_wanted_command": {
                            "name": "🔍 Проверить фото",
                            "switch_inline_query_current_chat": "search_wanted (приложи фотографию к этому сообщению и отправляй)",
                            "button_style": "primary",
                        }
                    }
                },
            },
        },
        "games": {
            "name": "🎮 Игры",
            "description": "Игры в Telegram, Roblox и Игра Василия™️.",
            "aliases": ["games"],
            **sf7_button_icon("gamecontroller"),
            "children": {
                "vasilii_game": {
                    "name": "🎲 Игра Василия™️ (post-wallet)",
                    "description": 'Василий предлагает сыграть в следующую ||уже бесплатную|| игру:\n- вы пишете /start_free_vasilii_game.\n- Василий 100 раз подбрасывает кубик 🎲\n- каждый раз, когда выпадает 4-6, ваш выигрыш удваивается\n- каждый раз, когда выпадает 1-3, ваш выигрыш уменьшается в 4 раза\n- ваш начальный выигрыш равен начальной ставке в 1000 вымышленных тугриков\n\nЧтобы сыграть в ИГРУ ВАСИЛИЯ™️, пришли сюда /start_free_vasilii_game. Пост-валлет версия, без крипты и кредитов 😎.\nПо мотивам [вот этого поста](https://t.me/ch_an/1864).',
                    "telegram_file_id": 'BQADAgAD8pwAAm8JmUlKxffmZspcsgI',
                    "aliases": ["vasilii_game"],
                },
                "telegram": {
                    "name": "📱 Телеграм веб-игры",
                    "description": "Запускаются прямо в Telegram.",
                    "children": {
                        "subway_surfers": {
                            "name": "🏄 Subway Surfers 👮‍♂️",
                            "url": "https://t.me/PlaySubwaySurfersBot/subway_surfers",
                        },
                        "doodle_jump": {
                            "name": "🐸 Doodle Jump 🚀",
                            "url": "https://t.me/PlayDoodleJumpBot/doodle_jump",
                        },
                        "math_effect": {
                            "name": "🚄 Math Effect 🏯",
                            "url": "https://t.me/PlayMathEffectBot/math_effect",
                        },
                    },
                },
                "roblox": {
                    "name": "🧱 Roblox",
                    "children": {
                        "life_grid": {
                            "name": "🧬 Life Grid",
                            "description": (
                                "Да, я сделал Game of Life в Roblox.\n\n"
                                "См. [пост](https://t.me/ch_an/2393)."
                            ),
                            "aliases": ["life_grid"],
                            "children": {
                                "go_to_life_grid": {
                                    "name": "🎮 Открыть в Roblox",
                                    "url": "https://www.roblox.com/share?code=ef23b71d9a2525459993f5074f0b90f4&type=ExperienceDetails",
                                    "button_style": "primary",
                                },
                            },
                        },
                    },
                },
            },
        },
        "other": {
            "name": "📦 Другое",
            **sf7_button_icon("archivebox"),
            "children": {
                "my_folder": {
                    "name": "📂 Моя папка",
                    "description": "📁 Здесь вы найдёте личные файлы, изображения и аудиозаписи, сохранённые мной.",
                    **sf7_button_icon("folder"),
                    "children": {
                        "shortcuts": {
                            "name": "🚀 Скрипты Shortcuts",
                            "description": "🔧 Здесь собраны мои скрипты для программы [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334), помогающие автоматизировать повседневные задачи.",
                            "disable_web_page_preview": 1,
                            "aliases": ["shortcuts"],
                            "children": {
                                "add_leetcode_daily_problem_solving_event": {
                                    "name": "📆 Add LeetCode daily problem solving event.shortcut",
                                    "description": '📆 **Add LeetCode daily problem solving event.shortcut**\n\nДобавляет событие в календарь на сегодняшнюю задачу в LeetCode.',

                                    "telegram_file_id": 'BQADAgADC5gAAm8JmUmVPYn5f3767gI',
                                    "hide_name": 1,
                                },
                                "run_ysh_scenario": {
                                    "name": "🏡 Run YSH Scenario.shortcut",
                                    "description": '🏡 **Run YSH Scenario.shortcut**\n\nЗапускает сценарий из Приложения Умного Дома Яндекса. Работает только на Mac.',

                                    "telegram_file_id": 'BQADAgADD5gAAm8JmUn_YxKoejEDvAI',
                                    "hide_name": 1,
                                },
                                "minecraft_server_online": {
                                    "name": "🐷 Minecraft server online.shortcut",
                                    "description": '🐷 **Minecraft server online.shortcut**\n\nПоказывает онлайн майнкрафт сервера и (при возможности) никнеймы игроков.',

                                    "telegram_file_id": 'BQADAgADDpgAAm8JmUmHwAryCIs_UAI',
                                    "hide_name": 1,
                                },
                                "hotspot_qr": {
                                    "name": "📶 Hotspot QR.shortcut",
                                    "description": '📶 **Hotspot QR.shortcut**\n\nВключает раздачу интернета на телефоне, и генерирует удобный экран, на котором есть название+пароль от WiFi сети, а также QR-код для быстрого подключения.',

                                    "telegram_file_id": 'BQADAgADDZgAAm8JmUkQUb6_C2aT8QI',
                                    "hide_name": 1,
                                },
                                "vasilii_game": {
                                    "name": "🎲 Vasilii Game.shortcut",
                                    "description": '🎲 **Vasilii Game.shortcut**\n\nКлон хеш-игры Василия (@vas100bot), написанный в Shortcuts.',

                                    "telegram_file_id": 'BQADAgADEJgAAm8JmUmLSAOWKUTxIgI',
                                    "hide_name": 1,
                                },
                                "calculate_text": {
                                    "name": "🧮 Calculate text.shortcut",
                                    "description": '🧮 **Calculate text.shortcut**\n\nВычисляет выражение из текстовой строки. Работает круче стандартного калькулятора, например, подсчитает sin(20)^2+cos(20)^2.',

                                    "telegram_file_id": 'BQADAgADDJgAAm8JmUmZVk2plFv6CgI',
                                    "hide_name": 1,
                                },
                                "szhat_photo": {
                                    "name": "🗜 Сжать Фото.shortcut",
                                    "description": '🗜 **Сжать Фото.shortcut**\n\nКонвертирует множество фото по фильтру в HEIF, сохраняет оригинальные метаданные и время создания.\nПо мотивам https://t.me/ch_an/2289',

                                    "telegram_file_id": 'BQADAgADCpgAAm8JmUnzWFr9S81bQAI',
                                    "hide_name": 1,
                                },
                            }
                        },
                        "emojis_and_stickers": {
                            "name": "😊 Папка для стикерпаков и эмодзипаков",
                            "aliases": ["emojis_and_stickers"],
                            "children": {
                                "new_apple_icons_emojis": {
                                    "name": "🍎🫙 Liquid Glass",
                                    "url": "https://t.me/addemoji/AppleAppsIcons",
                                },
                                "old_apple_icons_emojis": {
                                    "name": "🍏 Старые иконки приложений  Apple",
                                    "url": "https://t.me/addemoji/AppleIconsIOS",
                                },
                                "sf7_emoji_packs": _build_sf7_emoji_pack_tree(),
                            }
                        },
                        "other": {
                            "name": "Другое",
                            "children": {
                                "photo.jpg": {
                                    "name": "🖼️ photo.png",
                                    "telegram_file_id": 'BQADAgAD8JwAAm8JmUnwxgIgp9lVnQI',
                                },
                                "photo2.jpg": {
                                    "name": "🖼️ photo2.png",
                                    "telegram_file_id": 'BQADAgAD8ZwAAm8JmUn_GQABueMfx7AC',
                                },
                                "audio_01.mp3": {
                                    "name": "🎵 audio_01.mp3",
                                    "telegram_file_id": 'CQADAgADEZgAAm8JmUkzP34w1TB3KAI',
                                },
                                "Naya.mp4": {
                                    "name": "🎥 Naya.mp4",
                                    "telegram_file_id": 'BAADAgADCJgAAm8JmUnIq3P8xA5ATAI',
                                },
                                "Хорошие новости №11.pdf": {
                                    "name": "📄 Хорошие новости №11.pdf",
                                    "telegram_file_id": 'BQADAgADBJgAAm8JmUl1etUPD8MkSwI',
                                },
                                "CNOLM_Win.zip": {
                                    "name": "📦 CNOLM_Win.zip",
                                    "description": '**📦 CNOLM_Win.zip**',

                                    "telegram_file_id": 'BQADAgADB5gAAm8JmUnaQcg8fKzxGQI',
                                    "hide_name": 1,
                                },
                                "Presentation защита ВКР.zip": {
                                    "name": "📦 Presentation защита ВКР.zip",
                                    "description": '**📦 Presentation защита ВКР.zip**',

                                    "telegram_file_id": 'BQADAgADCZgAAm8JmUnkSm8xswRh8QI',
                                    "hide_name": 1,
                                },
                            }
                        }
                    },
                },
                "about_me": {
                    "name": "🔗 Ссылки на меня",
                    "description": "👤 Здесь вы найдете ссылки на меня.",
                    "aliases": ["about_me"],
                    **sf7_button_icon("person.crop.circle"),
                    "children": {
                        "telegram_channel": {
                            "name": "📢 Telegram-канал",
                            "url": "https://t.me/ch_an"
                        },
                        "telegram_channel_group": {
                            "name": "💬 Группа канала",
                            "url": "https://t.me/wallet_chat"
                        },
                        "telegram_bot": {
                            "name": "🤖 Telegram-бот (этот самый)",
                            "url": "https://t.me/dot_ch_bot"
                        },
                        "website": {
                            "name": "😎 Веб-сайт",
                            "url": "https://anatoliy.ch/"
                        },
                        "source_code": {
                            "name": "⌨️ Исходный код · AGPL-3.0",
                            "url": "https://github.com/ch3pasov/dot_ch_radio",
                        }
                    }
                },
                "language": {
                    "name": "🌐 Язык бота",
                    "description": (
                        "Бот выбирает язык по языку интерфейса Telegram. Если Telegram на русском, "
                        "бот отвечает по-русски; для всех остальных языков используется английский.\n\n"
                        "Чтобы изменить язык: **Telegram → Настройки → Язык**. После изменения "
                        "заново откройте меню или отправьте /start."
                    ),
                    "aliases": ["language"],
                    **sf7_button_icon("character.bubble"),
                },
                "my_data": {
                    "name": "Мои данные",
                    "parse_mode": "html",
                    "description": (
                        "<b>Центр управления данными</b>\n\n"
                        "Здесь можно проверить постоянные хранилища приложения, "
                        "получить полную выгрузку или безвозвратно удалить всё, что "
                        "бот хранит о вас.\n\n"
                        "Операции относятся только к данным самого приложения, "
                        "не к истории чата в Telegram."
                    ),
                    "aliases": ["my_data"],
                    "children_columns": 2,
                    **sf7_button_icon("externaldrive"),
                    **sf7_title_icon("externaldrive"),
                    "actions": {
                        "audit": {
                            "text": "🔎 Провести аудит",
                            "callback_data": "data_rights:audit",
                            "button_style": "primary",
                            **sf7_button_icon("magnifyingglass"),
                        },
                        "home": {
                            "text": "↩️ В центр данных",
                            "callback_data": "data_rights:home",
                            **sf7_button_icon("house"),
                        },
                        "copy_summary": {
                            "text": "📋 Скопировать итог",
                            "copy_text": "@dot_ch_bot · найдено 0 · удалено 0 · хранится 0 Б",
                            **sf7_button_icon("rectangle.on.rectangle"),
                        },
                        "takeout": {
                            "text": "📦 Takeout",
                            "callback_data": "data_rights:takeout",
                            "button_style": "success",
                            "message_effects": ["🎉", "👍"],
                            **sf7_button_icon("shippingbox"),
                        },
                        "delete": {
                            "text": "🗑 Удалить",
                            "callback_data": "data_rights:delete",
                            "button_style": "danger",
                            **sf7_button_icon("trash"),
                        },
                        "delete_confirm": {
                            "text": "🗑 Удалить безвозвратно",
                            "callback_data": "data_rights:delete_confirm",
                            "button_style": "danger",
                            "message_effects": ["🎉", "🔥", "👍"],
                            **sf7_button_icon("trash"),
                        },
                        "retry_audit": {
                            "text": "↻ Повторить",
                            "callback_data": "data_rights:audit",
                            **sf7_button_icon("arrow.clockwise"),
                        },
                        "retry_takeout": {
                            "text": "↻ Повторить",
                            "callback_data": "data_rights:takeout",
                            **sf7_button_icon("arrow.clockwise"),
                        },
                        "retry_delete": {
                            "text": "↻ Повторить",
                            "callback_data": "data_rights:delete",
                            "button_style": "danger",
                            **sf7_button_icon("arrow.clockwise"),
                        },
                        "retry_delete_confirm": {
                            "text": "↻ Повторить",
                            "callback_data": "data_rights:delete_confirm",
                            "button_style": "danger",
                            **sf7_button_icon("arrow.clockwise"),
                        },
                    },
                    "views": {
                        "result": {
                            "rows": [
                                ["copy_summary"],
                                ["takeout", "delete"],
                                ["home"],
                            ],
                        },
                        "document": {"rows": [["copy_summary"]]},
                        "delete_confirmation": {
                            "rows": [["delete_confirm"], ["home"]],
                        },
                        "deletion_result": {"rows": [["copy_summary"], ["home"]]},
                        "error_audit": {"rows": [["retry_audit"], ["home"]]},
                        "error_takeout": {"rows": [["retry_takeout"], ["home"]]},
                        "error_delete": {"rows": [["retry_delete"], ["home"]]},
                        "error_delete_confirm": {
                            "rows": [["retry_delete_confirm"], ["home"]],
                        },
                    },
                    "children": {
                        "audit": {
                            "name": "🔎 Провести аудит",
                            "callback_data": "data_rights:audit",
                            "button_style": "primary",
                            **sf7_button_icon("magnifyingglass"),
                        },
                        "takeout": {
                            "name": "📦 Получить takeout",
                            "callback_data": "data_rights:takeout",
                            "button_style": "success",
                            **sf7_button_icon("shippingbox"),
                        },
                        "delete": {
                            "name": "🗑 Удалить всё",
                            "callback_data": "data_rights:delete",
                            "button_style": "danger",
                            "break_before": True,
                            "break_after": True,
                            **sf7_button_icon("trash"),
                        },
                    },
                },
                "secret_place": {
                    "name": "🔒 NDA папка",
                    "beta_access": 1,
                    "description": "👀 Если вы её видите, то вам это разрешили.",
                    **sf7_button_icon("lock"),
                    "children": {
                        "clique": {
                            "name": "㊙️ Клика",
                            "url": "https://t.me/sCliqueBot",
                        },
                        "delo": {
                            "name": "🤫 Дело",
                            "description": "См. [пост](https://t.me/ch_an/1884).",
                            "aliases": ["delo"],
                            "children": {
                                "go_to_delo": {
                                    "name": "🎧 Перейти к ДЕЛУ",
                                    "url": "https://t.me/dot_ch_delo_bot?start=start",
                                },
                            },
                        },
                        "minecraft_server": {
                            "name": "⛏️ Анатолий Ч. | minecraft-сервер",
                            "custom": "minecraft_server",
                            "refresh": 1,
                            "aliases": ["minecraft_server"],
                            "disable_web_page_preview": 1,
                            "children": {
                                "server-map": {
                                    "name": "🗺️ Карта сервера",
                                    "url": "https://map.anatoliy.ch",
                                },
                                "server-login": {
                                    "name": "🔑 Вход на сервер",
                                    "url": "https://t.me/mc_ch_bot"
                                },
                                "server-chat": {
                                    "name": "💬 Чат сервера",
                                    "url": "https://t.me/wallet_chat"
                                },
                                "server_voicechat": {
                                    "name": "🎙️ Голосовой чат сервера",
                                    "url": "https://t.me/ch_an?livestream"
                                }
                            }
                        },
                    }
                },
            },
        }
    }
}

common_tree = normalize_tree(common_tree)
common_trees = {
    RU: common_tree,
    EN: localize_content_tree(common_tree, EN),
}


def content_tree_for_locale(locale):
    return common_trees[normalize_locale(locale)]

startup_url = "https://zvukipro.com/uploads/files/2020-12/1609413715_the-microsoft-sound.mp3"

default_url = "https://live.lofiradio.ru/lofi_mp3_128"

wanted_not_found = """**🔍 Проверка завершена**

В результате проверки фотографии по базам данных розыска информация о наличии на фото лиц, находящихся в розыске, **не была обнаружена**. Это означает, что среди изображений на фотографии не найдено совпадений с данными розыска."""
wanted_found = """**🔍 Проверка завершена**

В результате проверки фотографии по базам данных розыска информация о наличии на фото лиц, находящихся в розыске, **была обнаружена**. Это означает, что среди изображений на фотографии найдены совпадения с данными розыска."""


def wanted_not_found_text(locale=RU):
    return localized(
        locale,
        ru=wanted_not_found,
        en=(
            "**🔍 Check complete**\n\n"
            "The photo was checked against wanted-person databases. No matches were found."
        ),
    )


def wanted_found_text(locale=RU):
    return localized(
        locale,
        ru=wanted_found,
        en=(
            "**🔍 Check complete**\n\n"
            "The photo was checked against wanted-person databases. One or more matches were found."
        ),
    )
