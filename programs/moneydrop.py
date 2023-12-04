from volume.config.debug import disable_moneydrops

if not disable_moneydrops:
    from global_vars import app_robot, app_dj, print
    from pyrogram import filters
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from volume.config.tg_ids import dot_ch_id, dot_ch_chat_id
    from volume.config.moneydrop_config import money_drop_amount, money_chat_id, money_drop_delay, money_drop_random_delay
    import asyncio
    from random import random
    last_media_group_id = 0

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
