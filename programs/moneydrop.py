from volume.config.debug import disable_moneydrops
from volume.config.moneydrop_config import money_drop_amount, money_chat_id, money_drop_delay, money_drop_random_delay
from global_vars import app_robot, app_dj, print
from pyrogram.enums.chat_action import ChatAction
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import re


async def send_money(
    chat_id,
    reply_to_message_id,
    text, button_text, debug_comment,
    amount=money_drop_amount
):

    assert amount >= 0.0001, "wallet не позволяет отправлять меньше 0.0001 TON!"
    assert amount < 0.5, "МНОГО ДЕНЕГ"

    r = await app_dj.get_inline_bot_results('@wallet', str(amount))
    result = r.results[0]
    if "TON" in result.title and "BTC" not in result.title:
        # создание чека в биллинге
        updates = (await app_dj.send_inline_bot_result(money_chat_id, r.query_id, result.id)).updates
        billing_message_id = updates[0].id

        # создание дебаг-сообщения в биллинге
        await app_robot.send_message(
            money_chat_id,
            f"amount={amount}\nchat_id={chat_id}\n{debug_comment}",
            reply_to_message_id=billing_message_id
        )
        print(f"amount={amount}\tchat_id={chat_id}\t{debug_comment}")
        # отправка чека адресату
        await app_robot.send_message(
            chat_id,
            text=text,
            reply_to_message_id=reply_to_message_id,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            button_text,
                            url=result.send_message.reply_markup.rows[0].buttons[0].url
                        )
                    ]
                ]
            )
        )
    else:
        raise ValueError("BTC! СЛЕВА НАПРАВО")


if not disable_moneydrops:
    from pyrogram import filters
    from volume.config.tg_ids import dot_ch_id, dot_ch_chat_id
    from random import random
    last_media_group_id = 0

    async def money_drop(
        money_drop_message_id,
        dot_ch_chat_id=dot_ch_chat_id,
        amount=money_drop_amount
    ):
        await send_money(
            dot_ch_chat_id,
            reply_to_message_id=money_drop_message_id,
            text='💸 **money drop.** 💸\n__Легендарное возвращение.__\nКто первый встал того и тапки!',
            button_text=f'Получить {amount}+ε на @wallet',
            debug_comment='money drop',
        )

    async def start_post_moneydrop_handlers():
        @app_robot.on_message(filters.linked_channel)
        async def my_handler(client, message):
            global last_media_group_id
            if message.sender_chat.id == dot_ch_id and message.chat.id == dot_ch_chat_id:
                if message.media_group_id != last_media_group_id:
                    last_media_group_id = message.media_group_id if message.media_group_id else 0
                    sleep_time = money_drop_delay+money_drop_random_delay*random()
                    # sleep_time = 300+300*random()
                    print(f'New post! Sleep {sleep_time}')
                    await asyncio.sleep(sleep_time)
                    print('Post-moneydrop!')
                    await money_drop(
                        message.id,
                    )
else:
    async def start_post_moneydrop_handlers():
        pass


async def count_credit(message, step_sleep):
    score = 0
    credit = 0.1
    for i in range(100):
        await asyncio.sleep(step_sleep)
        if (await app_robot.send_dice(message.chat.id, "🎲", disable_notification=True)).dice.value <= 3:
            credit *= 0.25
            continue
        credit *= 2
        score += 1
        if score >= 68:
            print("secret!")
            return await count_credit(message, step_sleep=step_sleep)
    return credit


async def vasilii_game(message, check_id):
    get_money_message_id = (
        await app_dj.send_message(
            "wallet",
            f"/start {check_id}"
        )
    ).id
    await app_robot.send_message(
        message.chat.id,
        "Принимаю чек...",
    )
    await app_robot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await asyncio.sleep(10)

    smth_wrong = True
    async for history_message in app_dj.get_chat_history("wallet", limit=10):
        if history_message.id == get_money_message_id:  # сообщения до нашей попытки взять денег игнорируем
            break
        if history_message.from_user.id != 1985737506:  # сообщения не от wallet игнорируем
            continue
        if not history_message.reply_markup:  # сообщения о том, что кто-то получил деньги от биллинга без кнопок игнорируем
            continue
        if "BTC" in history_message.text:  # сообщения с BTC игнорируем
            continue
        search = re.search(r"(\d+\.\d+) TON", history_message.text)
        if not search:  # сообщения без TON игнорируем
            continue
        amount = search.group(1)
        if amount != "0.1":  # сообщения с не 0.1 игнорируем
            continue
        smth_wrong = False
        break
    if smth_wrong:
        await app_robot.send_message(
            message.chat.id,
            "Что-то пошло не так. Попробуйте ещё раз."
        )
        return
    await app_robot.send_message(
        message.chat.id,
        "Запускаю ИГРУ ВАСИЛИЯ!",
    )
    credit = await count_credit(message, step_sleep=0.5)
    if credit < 0.0001:
        vasilii_game_message = await app_robot.send_message(
            message.chat.id,
            f"Ваш выигрыш меньше минимальной суммы чека: {credit} TON. Держи утешительный приз!"
        )
        win_sum = 0.0001
    elif credit < 0.1:
        vasilii_game_message = await app_robot.send_message(
            message.chat.id,
            f"Ваш выигрыш: {credit} TON."
        )
        win_sum = credit
    else:
        vasilii_game_message = await app_robot.send_message(
            message.chat.id,
            f"Ваш выигрыш: {credit} TON. Поздравляю!"
        )
        win_sum = credit
    await send_money(
        message.chat.id,
        vasilii_game_message.id,
        text='Выигрыш за ИГРУ ВАСИЛИЯ!',
        button_text=f'Получить {win_sum} на @wallet',
        debug_comment='vasilii game',
        amount=win_sum
    )
