from typing import Optional
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.text_utils import esc
from app.models.enums import UserRole
from app.models.user import User

router = Router(name="start")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    current_user: User,
    session: Optional[AsyncSession] = None,
    is_new_user: bool = False,
):
    """
    /start buyrug'i handleri.
    Guruhi hali biriktirilmagan foydalanuvchi uchun ro'yxatdan o'tish (universitet/
    fakultet/guruh) bosqichini boshlaydi, aks holda roliga mos menyuni ochadi.
    """
    name = esc(current_user.first_name) or "Talaba"

    if current_user.role == UserRole.ADMIN:
        welcome_text = f"👋 <b>Salom, {name}!</b>\n\nSiz administratorsiz. Kerakli bo'limni tanlang."
    else:
        welcome_text = (
            f"👋 <b>Salom, {name}!</b>\n\n"
            f"Men dars jadvalingizni saqlayman va har bir darsdan oldin eslatib turaman."
        )

    if not current_user.group_id:
        await message.answer(welcome_text, parse_mode="HTML")
        await start_registration(message, state, session)
        return

    kb = get_admin_main_keyboard() if current_user.role == UserRole.ADMIN else get_user_main_keyboard()
    await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb)
