from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from app.core.config import settings


def get_mini_app_inline_button(text: str = "📱 Mini Appni ochish", url: str = settings.MINI_APP_URL) -> InlineKeyboardMarkup:
    """Mini App ochish inline tugmasi"""
    keyboard = [
        [
            InlineKeyboardButton(
                text=text,
                web_app=WebAppInfo(url=url),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
