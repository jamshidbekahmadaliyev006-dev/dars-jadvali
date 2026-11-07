from html import escape
from typing import Any


def esc(value: Any) -> str:
    """
    Telegram parse_mode='HTML' xabarlariga qo'yiladigan har qanday foydalanuvchi yoki AI
    tomonidan taqdim etilgan matnni xavfsiz tarzda escape qiladi (masalan talabaning ismi,
    username'i, o'zi yozgan universitet/fakultet/guruh nomi, AI o'qigan fan/o'qituvchi nomi).
    Shu orqali HTML teglari (<a>, <b> va h.k.) orqali xabar formatini buzish yoki boshqa
    foydalanuvchilarni/adminni aldovchi havolalar joylashtirish oldi olinadi.
    """
    if value is None:
        return ""
    return escape(str(value), quote=False)
