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
        InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
    ]])


def admin_review_keyboard(submission_id: int, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_approve"), callback_data=f"approve_sub_{submission_id}"),
        InlineKeyboardButton(text=t(lang, "btn_reject"), callback_data=f"reject_sub_{submission_id}"),
    ]])


def reminder_minutes_keyboard(lang: str = DEFAULT_LANG, enabled: bool = True) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_15"), callback_data="remind_15"),
            InlineKeyboardButton(text=t(lang, "btn_30"), callback_data="remind_30"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_45"), callback_data="remind_45"),
            InlineKeyboardButton(text=t(lang, "btn_60"), callback_data="remind_60"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_remind_off" if enabled else "btn_remind_on"),
                              callback_data="remind_off" if enabled else "remind_on")],
    ])


_DAY_BUTTONS = {
    "uz": ["Du", "Se", "Ch", "Pa", "Ju", "Sh"],
    "ru": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
    "en": ["Mo", "Tu", "We", "Th", "Fr", "Sa"],
}


def week_days_keyboard(lang: str = DEFAULT_LANG, active: int = -1) -> InlineKeyboardMarkup:
    """Dars jadvali ostidagi kun tugmalari: bosilganda xabar o'sha joyida almashadi"""
    days = _DAY_BUTTONS.get(lang, _DAY_BUTTONS[DEFAULT_LANG])
    row = [
        InlineKeyboardButton(text=f"• {name} •" if i == active else name, callback_data=f"day_{i}")
        for i, name in enumerate(days)
    ]
    footer = InlineKeyboardButton(
        text=f"• {t(lang, 'btn_week_all')} •" if active == -1 else t(lang, "btn_week_all"),
        callback_data="day_all",
    )
    change = InlineKeyboardButton(text=t(lang, "btn_schedule_changed"), callback_data="sched_change")
    return InlineKeyboardMarkup(inline_keyboard=[row, [footer], [change]])


def profile_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "btn_change_group"), callback_data="profile_group")],
        [InlineKeyboardButton(text=t(lang, "btn_change_language"), callback_data="profile_lang")],
    ])


def contact_reply_keyboard(user_telegram_id: int, lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_reply"), callback_data=f"contact_reply_{user_telegram_id}"),
    ]])


def announcement_confirm_keyboard(lang: str = DEFAULT_LANG) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_send_now"), callback_data="announce_send"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="announce_cancel"),
    ]])
