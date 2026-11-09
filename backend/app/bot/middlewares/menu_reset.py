from typing import Any, Awaitable, Callable, Dict, Set
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from app.bot.i18n import TEXTS, labels

_MENU: Set[str] = set()


def menu_labels() -> Set[str]:
    if not _MENU:
        for key in TEXTS:
            if key.startswith("btn_"):
                _MENU.update(labels(key))
    return _MENU


class MenuResetMiddleware(BaseMiddleware):
    """
    Foydalanuvchi biror narsa kutilayotgan holatda (masalan "Eslatma" bosilib, vaqt yozilishi kutilayotgan paytda)
    boshqa menyu tugmasini bossa, kutilayotgan holat bekor qilinadi va bosilgan tugma o'z ishini qiladi.
    Ro'yxatdan o'tish (universitet/fakultet/guruh) bosqichlari bundan mustasno emas: tugma bosilsa - menyuga qaytadi.
    """

    async def __call__(self, handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                       event: TelegramObject, data: Dict[str, Any]) -> Any:
        if isinstance(event, Message) and event.text and event.text.strip() in menu_labels():
            state = data.get("state")
            if state is not None:
                try:
                    if await state.get_state() is not None:
                        await state.clear()
                except Exception:
                    pass
        return await handler(event, data)
