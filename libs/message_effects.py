"""Process-local Telegram message-effect catalogue and safe send retry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

from telethon.errors import RPCError
from telethon.tl.functions.messages import GetAvailableEffectsRequest


ResultT = TypeVar("ResultT")


class MessageEffectCatalog:
    """An in-memory map from effect emoticons to Telegram effect ids."""

    def __init__(self) -> None:
        self._ids: dict[str, int] = {}

    def clear(self) -> None:
        self._ids.clear()

    @property
    def size(self) -> int:
        return len(self._ids)

    def snapshot(self) -> dict[str, int]:
        return dict(self._ids)

    async def load(self, user_client) -> int:
        """Refresh non-premium effects; a failed refresh disables effects."""

        try:
            result = await user_client(GetAvailableEffectsRequest(hash=0))
            loaded = {
                effect.emoticon: int(effect.id)
                for effect in getattr(result, "effects", ())
                if (
                    isinstance(getattr(effect, "emoticon", None), str)
                    and getattr(effect, "id", None) is not None
                    and not getattr(effect, "premium_required", False)
                )
            }
        except Exception:
            self.clear()
            return 0

        # Replace atomically from the perspective of single-threaded asyncio
        # readers; never persist catalogue data between processes.
        self._ids = loaded
        return len(loaded)

    def resolve(self, preferred_emoticons: Iterable[str]) -> int | None:
        if isinstance(preferred_emoticons, (str, bytes)):
            raise TypeError("preferred_emoticons must be an iterable of emoticon strings")
        for emoticon in preferred_emoticons:
            if not isinstance(emoticon, str):
                raise TypeError("preferred_emoticons must contain only strings")
            effect_id = self._ids.get(emoticon)
            if effect_id is not None:
                return effect_id
        return None


MESSAGE_EFFECTS = MessageEffectCatalog()


async def load_message_effects(user_client) -> int:
    return await MESSAGE_EFFECTS.load(user_client)


def resolve_message_effect(preferred_emoticons: Iterable[str]) -> int | None:
    return MESSAGE_EFFECTS.resolve(preferred_emoticons)


def is_message_effect_error(error: RPCError) -> bool:
    """Identify Telegram RPC errors for an unavailable/invalid effect only."""

    detail = f"{type(error).__name__} {error}".upper()
    return "EFFECT" in detail


async def send_with_effect_retry(
    send: Callable[[int | None], Awaitable[ResultT]],
    effect_id: int | None,
) -> ResultT:
    """Send once with an effect, retrying only effect-specific RPC errors.

    ``send`` receives the current effect id.  It is responsible for passing it
    as ``message_effect_id`` and for rewinding any in-memory file before each
    call.  Flood, network, permission and all other RPC failures propagate.
    """

    try:
        return await send(effect_id)
    except RPCError as error:
        if effect_id is None or not is_message_effect_error(error):
            raise
        return await send(None)
