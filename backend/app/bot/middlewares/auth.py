from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.services.user_service import UserService


class AuthMiddleware(BaseMiddleware):
    """
    Foydalanuvchini bazadan avtomatik tekshiruvchi va contextga 'current_user' sifatida yuklovchi middleware.
    Agar yangi foydalanuvchi bo'lsa, avtomatik ravishda bazaga USER yoki ADMIN sifatida ro'yxatga oladi.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser = data.get("event_from_user")
        session: AsyncSession = data.get("session")

        if not tg_user or not session:
            return await handler(event, data)

        try:
            user, is_new = await UserService.get_or_create_user(
                session=session,
                telegram_id=tg_user.id,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                username=tg_user.username,
                language_code=tg_user.language_code or "uz",
            )

            if not user.is_active:
                if isinstance(event, Message):
                    await event.answer("⚠️ Kechirasiz, sizning hisobingiz tizim tomonidan bloklangan.")
                return

            data["current_user"] = user
            data["is_new_user"] = is_new
            return await handler(event, data)
        except Exception as e:
            logger.error(f"Error in AuthMiddleware for user {tg_user.id}: {e}")
            raise
