from volume.config.tg_ids import admins


def admin_only(func):
    async def wrapper(client, message, *args, **kwargs):
        if message.from_user.id in admins:
            return await func(client, message, *args, **kwargs)
        else:
            return "🧚‍♀️"
    return wrapper
