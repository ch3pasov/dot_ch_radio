import json
from pathlib import Path

from volume.content_schema import folder, link, normalize_tree


EMOJI_PACK_LINKS_PATH = Path(__file__).resolve().parent.parent / "config" / "emoji_pack_links.json"




def _build_sf7_emoji_pack_tree():
    with EMOJI_PACK_LINKS_PATH.open(encoding="utf-8") as links_file:
        links_config = json.load(links_file)

    weights = links_config["weights"]
    url_template = links_config["url_template"]
    set_name_template = links_config["set_name_template"]

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

    def group_pages(weight, page_size=11):
        group_items = list(groups.items())
        pages = []
        for page_index in range(0, len(group_items), page_size):
            page_items = group_items[page_index:page_index + page_size]
            first_title = page_items[0][1]["title"]
            last_title = page_items[-1][1]["title"]
            page_number = page_index // page_size + 1
            pages.append(
                folder(
                    f"{first_title} — {last_title}",
                    id=f"page_{page_number:02d}",
                    children_columns=1,
                    children=[
                        link(
                            f"{group['title']} ({group['count']})",
                            pack_url(weight, group_id),
                            id=group_id,
                            button_style="primary",
                        )
                        for group_id, group in page_items
                    ],
                )
            )
        return pages

    return folder(
        "🧩 SF7 эмодзипаки",
        description=(
            f"{links_config['packs_count']} эмодзипаков SF7: "
            f"{len(weights)} толщин × {len(groups)} групп."
        ),
        beta_access=1,
        children_columns=1,
        children=[
            folder(
                f"🔤 {weight}",
                id=weight.lower(),
                button_style="primary",
                children_columns=1,
                children=group_pages(weight),
            )
            for weight in weights
        ],
    )


common_tree = {
    "name": "🌳 Корень",
    "description": "👋 Добро пожаловать в корень дерева! Здесь начинается ваше путешествие по музыкальному миру и файлам.",
    "alias": "root",
    "children": {
        "radio": {
            "name": "📻 Радио",
            "description": "🎶 В этой секции вы найдете различные радиостанции и музыкальные потоки, доступные для прослушивания в https://t.me/ch_an?livestream",
            "alias": "radio",
            "children": {
                "go_to_radio": {
                    "name": "🔗 Перейти к радио",
                    "url": "https://t.me/ch_an?livestream"
                },
                "night_radio": {
                    "name": "🌙 Ночной эфир",
                    "alias": "night_radio",
                    "description": (
                        "По расписанию в канале включается **ночной режим**: вместо дневного радио идёт "
                        "отдельный ночной эфир.\n\n"
                        "**Время по UTC:** с **18:15** до **03:00** (через полночь по UTC); после трёх часов снова "
                        "обычное вещание. В этот промежуток из бота **нельзя переключать** станции — слушайте "
                        "ночной стрим в [лайве канала](https://t.me/ch_an?livestream).\n\n"
                        "Подробности и заметки — в [посте канала](https://t.me/ch_an/2387)."
                    ),
                },
                "lofi_girl": {
                    "name": "🎧 LoFi Girl",
                    "radio_url": "https://live.lofiradio.ru/lofi_mp3_128"
                },
                "radio_jazz": {
                    "name": "🎷 Радио Jazz Москва 89.1 FM",
                    "radio_url": "https://nashe1.hostingradio.ru/jazz-256",
                },
                "andon_fm": {
                    "name": "🤖 Andon FM",
                    "alias": "andon_fm",
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
                }
            }
        },
        "invert_picture": {
            "name": "💫 Правильная инверсия™️",
            "description": '🔘 Инвертирует изображение. [По настоящему!](https://ru.wikipedia.org/wiki/Инверсия_%28геометрия%29) Относительно окружности!',

            "telegram_file_id": 'BQADAgAD7pwAAm8JmUmhLedYHQzukAI',
            "alias": "invert_picture",
            "children": {
                "invert_picture_command": {
                    "name": "🔘 Инвертировать картинку",
                    "switch_inline_query_current_chat": "invert_picture (приложи фотографию к этому сообщению и отправляй)",
                }
            }
        },
        "vasilii_game": {
            "name": "🎲 Игра Василия™️ (post-wallet)",
            "description": 'Василий предлагает сыграть в следующую ||уже бесплатную|| игру:\n- вы пишите /start_free_vasilii_game.\n- Василий 100 раз подбрасывает кубик 🎲\n- каждый раз, когда выпадает 4-6, ваш выигрыш удваивается\n- каждый раз, когда выпадает 1-3, ваш выигрыш уменьшается в 4 раза\n- ваш начальный выигрыш равен начальной ставке в 1000 вымышленных тугриков\n\nЧтобы сыграть в ИГРУ ВАСИЛИЯ™️, пришли сюда /start_free_vasilii_game. Пост-валлет версия, без крипты и кредитов 😎.\nПо мотивам [вот этого поста](https://t.me/ch_an/1864).',

            "telegram_file_id": 'BQADAgAD8pwAAm8JmUlKxffmZspcsgI',
            "alias": "vasilii_game",
        },
        "foreign_languages": {
            "name": "🌐 Что-то на иностранном",
            "children": {
                "katakana_racism": {
                    "name": "🇯🇵 Руссуко-Японсукий пэрэводутику (простите)",
                    "description": 'Переводит любой текст с русского на японскую транслитерацию через катакану. Перевод генерируется [вот тут](https://nippon.temerov.org/rus_kana.php). Ещё раз, простите.',

                    "telegram_file_id": 'BQADAgAD7ZwAAm8JmUnXVfb1QoFRYgI',
                    "alias": "rus_to_katakana",
                    "children": {
                        "rus_to_katakana_command": {
                            "name": "🔡 Перевести текст",
                            "switch_inline_query_current_chat": "rus_to_katakana ",
                        }
                    }
                },
                "bashkir_haiku": {
                    "name": "🌸 Башкирские хокку",
                    "description": "Хокку генерируются [вот тут](http://nevmenandr.net/cgi-bin/haiku.html).\n",
                    "custom": "bashkir_haiku",
                    "refresh": 1,
                    "alias": "bashkir_haiku",
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
                    "alias": "turkic_names",
                    "beta_access": 0,
                },
            }
        },
        "web_games": {
            "name": "🎮 Веб-игры",
            "description": "🕹️ Игры в Telegram и ссылки на игры вне мессенджера.",
            "alias": "web_games",
            "children": {
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
                "other_web_games": {
                    "name": "🌐 Другие",
                    "children": {
                        "life_grid": {
                            "name": "🧬 Life Grid",
                            "description": (
                                "Да, я сделал Game of Life в Roblox.\n\n"
                                "См. [пост](https://t.me/ch_an/2393)."
                            ),
                            "alias": "life_grid",
                            "children": {
                                "go_to_life_grid": {
                                    "name": "🎮 Открыть в Roblox",
                                    "url": "https://www.roblox.com/share?code=ef23b71d9a2525459993f5074f0b90f4&type=ExperienceDetails",
                                },
                            },
                        },
                    },
                },
            },
        },
        "other": {
            "name": "📦 Другое",
            "children": {
                "search_wanted": {
                    "name": "🔍 Поиск по розыску",
                    "description": "👤 Инструмент для проверки нахождения людей в розыске. Обратите внимание: точность результатов не гарантируется, и данная система не должна использоваться как единственный источник информации при принятии важных решений.",
                    "alias": "search_wanted",
                    "children": {
                        "search_wanted_command": {
                            "name": "🔍 Проверить фото",
                            "switch_inline_query_current_chat": "search_wanted (приложи фотографию к этому сообщению и отправляй)",
                        }
                    }
                },
                "weather": {
                    "name": "🌤️ Погода",
                    "description": "🌡️ Показывает погоду в указанном городе. Для получения погоды скинь гео 🌚.",
                    "alias": "weather"
                },
                "my_folder": {
                    "name": "📂 Моя папка",
                    "description": "📁 Здесь вы найдете личные файлы, изображения и аудиозаписи, сохраненные мной.",
                    "children": {
                        "shortcuts": {
                            "name": "🚀 Скрипты Shortcuts",
                            "description": "🔧 Здесь собраны мои скрипты для программы [Shortcuts](https://apps.apple.com/us/app/shortcuts/id915249334), помогающие автоматизировать повседневные задачи.",
                            "disable_web_page_preview": 1,
                            "alias": "shortcuts",
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
                                    "description": '🗜 **Сжать Фото.shortcut**\n\nКонвертирует множество фото по фильтру в HEIF, сохраняет оригинальные метаданные и время создания).\nПо мотивам https://t.me/ch_an/2289',

                                    "telegram_file_id": 'BQADAgADCpgAAm8JmUnzWFr9S81bQAI',
                                    "hide_name": 1,
                                },
                            }
                        },
                        "emojis_and_stickers": {
                            "name": "😊 Папка для стикерпаков и эмодзипаков",
                            "alias": "emojis_and_stickers",
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
                    "alias": "about_me",
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
                        }
                    }
                },
                "secret_place": {
                    "name": "🔒 NDA папка",
                    "beta_access": 1,
                    "description": "👀 Если вы её видите, то вам это разрешили",
                    "children": {
                        "clique": {
                            "name": "㊙️ Клика",
                            "url": "https://t.me/sCliqueBot",
                        },
                        "nadezhdin": {
                            "name": "📝 Надеждин",
                            "custom": "nadezhdin",
                            "alias": "nadezhdin"
                        },
                        "delo": {
                            "name": "🤫 Дело",
                            "description": "См. [пост](https://t.me/ch_an/1884).",
                            "alias": "delo",
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
                            "alias": "minecraft_server",
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

startup_url = "https://zvukipro.com/uploads/files/2020-12/1609413715_the-microsoft-sound.mp3"

default_url = "https://live.lofiradio.ru/lofi_mp3_128"

wanted_not_found = """**🔍 Проверка завершена**

В результате проверки фотографии по базам данных розыска информация о наличии на фото лиц, находящихся в розыске, **не была обнаружена**. Это означает, что среди изображений на фотографии не найдено совпадений с данными розыска."""
wanted_found = """**🔍 Проверка завершена**

В результате проверки фотографии по базам данных розыска информация о наличии на фото лиц, находящихся в розыске, **была обнаружена**. Это означает, что среди изображений на фотографии найдены совпадения с данными розыска."""
