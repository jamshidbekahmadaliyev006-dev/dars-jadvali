from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from app.bot.handlers.registration import start_registration
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.text_utils import esc
from app.models.enums import UserRole
from app.models.user import User

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, current_user: User, is_new_user: bool = False):
    """
    /start buyrug'i handleri.
    Guruhi hali biriktirilmagan foydalanuvchi uchun ro'yxatdan o'tish (universitet/
    fakultet/guruh) bosqichini boshlaydi, aks holda roliga mos menyuni ochadi.
    """
    greeting = "Assalomu alaykum"
    name = esc(current_user.first_name) or "Talaba"

    if current_user.role == UserRole.ADMIN:
        welcome_text = (
            f"👑 <b>{greeting}, Administrator {name}!</b>\n\n"
            f"UniNotify boshqaruv tizimiga xush kelibsiz.\n"
            f"Bu yerdan universitetlar, jadvallar va foydalanuvchilarni nazorat qilishingiz mumkin."
        )
    else:
        welcome_text = (
            f"🎓 <b>{greeting}, {name}!</b>\n\n"
            f"<b>UniNotify</b> — universitet talabalari uchun universal platformaga xush kelibsiz!\n\n"
            f"🚀 <b>Imkoniyatlar:</b>\n"
            f"• Dars jadvalini screenshot orqali avtomatik tanib olish\n"
            f"• Darsdan necha daqiqa oldin xohlasangiz, shuncha vaqt oldin eslatma\n"
            f"• Har doim qo'l ostida: bugungi va ertangi darslar"
        )

    if not current_user.group_id:
        await message.answer(welcome_text, parse_mode="HTML")
        await start_registration(message, state)
        return

    kb = get_admin_main_keyboard() if current_user.role == UserRole.ADMIN else get_user_main_keyboard()
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb)
