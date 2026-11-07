from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from app.bot.keyboards.utils import mini_app_button_kwargs
from app.core.config import settings


def get_user_main_keyboard(mini_app_url: str = None) -> ReplyKeyboardMarkup:
    """Oddiy talabalar uchun asosiy menyu klaviaturasi"""
    target_url = mini_app_url or settings.MINI_APP_URL
    keyboard = [
        [
            KeyboardButton(
                text="📱 UniNotify Mini App",
                **mini_app_button_kwargs(target_url),
            )
        ],
        [
            KeyboardButton(text="📖 Bugungi darslar"),
            KeyboardButton(text="📆 Ertangi darslar"),
        ],
        [
            KeyboardButton(text="📅 Dars jadvalim"),
            KeyboardButton(text="📝 Vazifalarim"),
        ],
        [
            KeyboardButton(text="📤 Jadval yuborish"),
            KeyboardButton(text="📊 Jadval holati"),
        ],
        [
            KeyboardButton(text="⚙️ Sozlamalar"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_main_keyboard(mini_app_url: str = None) -> ReplyKeyboardMarkup:
    """Administratorlar uchun boshqaruv menyusi klaviaturasi"""
    target_url = mini_app_url or settings.MINI_APP_URL
    keyboard = [
        [
            KeyboardButton(
                text="📱 UniNotify Mini App",
                **mini_app_button_kwargs(target_url),
            )
        ],
        [
            KeyboardButton(text="📥 Yangi screenshotlar"),
            KeyboardButton(text="🗓 Dars jadvallari"),
        ],
        [
            KeyboardButton(text="🏛 Universitetlar"),
            KeyboardButton(text="🏢 Fakultetlar"),
            KeyboardButton(text="👥 Guruhlar"),
        ],
        [
            KeyboardButton(text="🚪 Binolar va xonalar"),
            KeyboardButton(text="👤 Foydalanuvchilar"),
        ],
        [
            KeyboardButton(text="📢 E’lonlar"),
            KeyboardButton(text="📈 Statistika"),
        ],
        [
            KeyboardButton(text="🎓 Talaba ko'rinishiga o'tish"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
