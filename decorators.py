from volume.config.tg_ids import admins, beta_testers


def _only(allowlist):
    def decorator(func):
        async def wrapper(client, message, *args, **kwargs):
            if message.from_user.id in allowlist:
                return await func(client, message, *args, **kwargs)
            else:
                return "🧚‍♀️"
        return wrapper
    return decorator


admin_only = _only(admins)
beta_testers_only = _only(beta_testers)
