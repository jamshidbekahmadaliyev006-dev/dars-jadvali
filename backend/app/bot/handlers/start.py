from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.models.enums import UserRole
from app.models.user import User

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message, current_user: User, is_new_user: bool = False):
    """
    /start buyrug'i handleri.
    Foydalanuvchi roliga qarab tegishli menyuni ochadi.
    """
    greeting = "Assalomu alaykum"
    name = current_user.first_name or "Talaba"

    if current_user.role == UserRole.ADMIN:
        welcome_text = (
            f"👑 <b>{greeting}, Administrator {name}!</b>\n\n"
            f"UniNotify boshqaruv tizimiga xush kelibsiz.\n"
            f"Bu yerdan universitetlar, jadvallar, screenshotlar va "
            f"foydalanuvchilarni to'liq nazorat qilishingiz mumkin.\n\n"
            f"Quyidagi boshqaruv menyusidan kerakli bo'limni tanlang:"
        )
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_admin_main_keyboard(),
        )
    else:
        welcome_text = (
            f"🎓 <b>{greeting}, {name}!</b>\n\n"
            f"<b>UniNotify</b> — universitet talabalari uchun universal platformaga xush kelibsiz!\n\n"
            f"🚀 <b>Imkoniyatlar:</b>\n"
            f"• Dars jadvalini qulay boshqarish\n"
            f"• Darsdan 15 daqiqa oldin avtomatik eslatmalar\n"
            f"• Jadval screenshotini AI orqali avtomatik aniqlash\n"
            f"• Zamonaviy Telegram Mini App orqali shaxsiy reja va vazifalar\n\n"
            f"Boshlash uchun pastdagi menyudan foydalaning yoki <b>UniNotify Mini App</b>'ni oching:"
        )
        await message.answer(
            welcome_text,
            parse_mode="HTML",
            reply_markup=get_user_main_keyboard(),
        )
