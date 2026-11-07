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


def admin_review_keyboard(submission_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_sub_{submission_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_sub_{submission_id}"),
    ]])


def reminder_minutes_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="10 daqiqa", callback_data="remind_10"),
            InlineKeyboardButton(text="15 daqiqa", callback_data="remind_15"),
        ],
        [
            InlineKeyboardButton(text="Yarim soat", callback_data="remind_30"),
            InlineKeyboardButton(text="1 soat", callback_data="remind_60"),
        ],
    ])


def announcement_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yuborish", callback_data="announce_send"),
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="announce_cancel"),
    ]])
