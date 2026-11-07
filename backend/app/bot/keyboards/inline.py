from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.bot.i18n import DEFAULT_LANG, t
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


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
    ]])


def admin_review_keyboard(submission_id: int, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_approve"), callback_data=f"approve_sub_{submission_id}"),
        InlineKeyboardButton(text=t(lang, "btn_reject"), callback_data=f"reject_sub_{submission_id}"),
    ]])


def reminder_minutes_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_10"), callback_data="remind_10"),
            InlineKeyboardButton(text=t(lang, "btn_15"), callback_data="remind_15"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_30"), callback_data="remind_30"),
            InlineKeyboardButton(text=t(lang, "btn_60"), callback_data="remind_60"),
        ],
    ])


def announcement_confirm_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_send_now"), callback_data="announce_send"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="announce_cancel"),
    ]])
