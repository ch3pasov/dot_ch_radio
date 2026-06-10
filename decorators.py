from volume.config.tg_ids import admins


def _only(allowlist):
    def decorator(func):
        async def wrapper(event, *args, **kwargs):
            if event.sender_id in allowlist:
                return await func(event, *args, **kwargs)
            try:
                await event.reply("🧚‍♀️")
            except Exception:
                pass
            return None
        return wrapper
    return decorator


admin_only = _only(admins)
# beta_testers_only = _only(beta_testers)
