from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import async_session
from db.models import User
from config import settings


class AuthMiddleware(BaseMiddleware):
    """
    Middleware авторизации.
    - Создаёт пользователя в БД при первом обращении.
    - Обновляет last_seen и username.
    - Пробрасывает объекты 'user' (ORM) и 'session' (AsyncSession) в хендлеры.
    - Если пользователь деактивирован — блокирует запрос.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Достаём tg-пользователя из апдейта
        tg_user = None
        if isinstance(event, Update):
            if event.message:
                tg_user = event.message.from_user
            elif event.callback_query:
                tg_user = event.callback_query.from_user

        if tg_user is None:
            return await handler(event, data)

        async with async_session() as session:
            db_user = await self._get_or_create(session, tg_user)

            if not db_user.is_active:
                # Заблокированный пользователь — ничего не делаем
                return

            # Пробрасываем в хендлер
            data["db_user"] = db_user
            data["session"] = session

            result = await handler(event, data)
            await session.commit()
            return result

    @staticmethod
    async def _get_or_create(session: AsyncSession, tg_user) -> User:
        from datetime import datetime, timezone

        stmt = select(User).where(User.tg_id == tg_user.id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)

        if user is None:
            # Первый вход — определяем роль
            if tg_user.id in settings.admin_ids_list:
                role = "admin"
            else:
                role = "client"  # все новые — клиенты, воркер назначается вручную
            user = User(
                tg_id=tg_user.id,
                username=tg_user.username,
                full_name=tg_user.full_name,
                role=role,
                last_seen=now,
            )
            session.add(user)
            await session.flush()
        else:
            user.last_seen = now
            user.username = tg_user.username
            user.full_name = tg_user.full_name

            # Синхронизируем роль если tg_id в ADMIN_IDS
            if tg_user.id in settings.admin_ids_list and user.role != "admin":
                user.role = "admin"

        return user
