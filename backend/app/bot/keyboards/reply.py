from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from app.bot.i18n import DEFAULT_LANG, t


def _button(lang: str, key: str) -> KeyboardButton:
    return KeyboardButton(text=t(lang, key))


def get_user_main_keyboard(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    """Talabalar uchun asosiy menyu"""
    keyboard = [
        [_button(lang, "btn_week")],
        [_button(lang, "btn_today"), _button(lang, "btn_tomorrow")],
        [_button(lang, "btn_reminder"), _button(lang, "btn_profile")],
        [_button(lang, "btn_contact")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_main_keyboard(lang: str = DEFAULT_LANG) -> ReplyKeyboardMarkup:
    """Administratorlar uchun boshqaruv menyusi"""
    keyboard = [
        [_button(lang, "btn_stats"), _button(lang, "btn_users")],
        [_button(lang, "btn_new_shots"), _button(lang, "btn_teachers")],
        [_button(lang, "btn_groups"), _button(lang, "btn_announce")],
        [_button(lang, "btn_student_view"), _button(lang, "btn_language")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
