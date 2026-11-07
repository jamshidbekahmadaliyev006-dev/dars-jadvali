from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_user_main_keyboard() -> ReplyKeyboardMarkup:
    """Oddiy talabalar uchun soddalashtirilgan asosiy menyu"""
    keyboard = [
        [
            KeyboardButton(text="📖 Bugungi darslar"),
            KeyboardButton(text="📆 Ertangi darslar"),
        ],
        [
            KeyboardButton(text="🗓 Umumiy jadval"),
            KeyboardButton(text="📤 Jadval yuborish"),
        ],
        [
            KeyboardButton(text="📊 Jadval holati"),
            KeyboardButton(text="⏰ Eslatma sozlamalari"),
        ],
        [
            KeyboardButton(text="👤 Profilim"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_admin_main_keyboard() -> ReplyKeyboardMarkup:
    """Administratorlar uchun soddalashtirilgan boshqaruv menyusi"""
    keyboard = [
        [
            KeyboardButton(text="📈 Statistika"),
            KeyboardButton(text="📥 Yangi screenshotlar"),
        ],
        [
            KeyboardButton(text="👤 Foydalanuvchilar"),
            KeyboardButton(text="📢 E’lonlar"),
        ],
        [
            KeyboardButton(text="🎓 Talaba ko'rinishiga o'tish"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
