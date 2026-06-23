from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser

from bukafit.db import repositories as repo
from bukafit.db.session import SessionMaker


class DBMiddleware(BaseMiddleware):
    """Открывает сессию на апдейт, кладёт session + user в data, коммитит в конце."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        async with SessionMaker() as session:
            data["session"] = session
            if tg_user is not None:
                data["user"] = await repo.get_or_create_user(session, tg_user.id)
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise
