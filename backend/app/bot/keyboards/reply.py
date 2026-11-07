from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_user_main_keyboard() -> ReplyKeyboardMarkup:
    """Talabalar uchun asosiy menyu"""
    keyboard = [
        [
            KeyboardButton(text="📖 Bugungi darslar"),
            KeyboardButton(text="📆 Ertangi darslar"),
        ],
        [KeyboardButton(text="🗓 Umumiy jadval")],
        [
            KeyboardButton(text="⏰ Eslatma sozlamalari"),
            KeyboardButton(text="📤 Jadval yuborish"),
        ],
        [KeyboardButton(text="👤 Profilim")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Administratorlar uchun boshqaruv menyusi"""
    keyboard = [
        [
            KeyboardButton(text="📥 Yangi screenshotlar"),
            KeyboardButton(text="📈 Statistika"),
        ],
        [
            KeyboardButton(text="👥 Guruhlar"),
            KeyboardButton(text="👤 Foydalanuvchilar"),
        ],
        [KeyboardButton(text="📢 E'lon yuborish")],
        [KeyboardButton(text="🎓 Talaba ko'rinishiga o'tish")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
