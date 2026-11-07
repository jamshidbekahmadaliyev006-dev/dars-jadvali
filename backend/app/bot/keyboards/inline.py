from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.bot.keyboards.utils import mini_app_button_kwargs
from app.core.config import settings


def get_mini_app_inline_button(text: str = "📱 Mini Appni ochish", url: str = None) -> InlineKeyboardMarkup:
    """Mini App ochish inline tugmasi"""
    target_url = url or settings.MINI_APP_URL
    keyboard = [
        [
            InlineKeyboardButton(
                text=text,
                **mini_app_button_kwargs(target_url),
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)
