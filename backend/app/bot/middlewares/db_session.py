from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.core.database import AsyncSessionLocal
from app.core.logging import logger


class DbSessionMiddleware(BaseMiddleware):
    """Har bir bot hodisasi uchun alohida AsyncSession yaratuvchi middleware"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Error during bot event processing: {e}")
                raise
