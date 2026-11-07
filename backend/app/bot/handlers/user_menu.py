from aiogram import F, Router
from aiogram.types import Message
from app.bot.keyboards.inline import get_mini_app_inline_button
from app.models.user import User

router = Router(name="user_menu")


@router.message(F.text == "📖 Bugungi darslar")
async def handle_today_lessons(message: Message, current_user: User):
    if not current_user.group_id:
        await message.answer(
            "ℹ️ <b>Siz hali o'z guruhingizni tanlamagansiz.</b>\n\n"
            "Dars jadvalini ko'rish uchun avval universitet va guruhingizni biriktiring yoki dars jadvali screenshotini yuboring.",
            parse_mode="HTML",
            reply_markup=get_mini_app_inline_button("📱 Mini App orqali guruh tanlash"),
        )
        return

    await message.answer(
        "📅 Bugungi darslar haqida ma'lumot yuklanmoqda...",
        parse_mode="HTML",
    )


@router.message(F.text == "📆 Ertangi darslar")
async def handle_tomorrow_lessons(message: Message, current_user: User):
    if not current_user.group_id:
        await message.answer(
            "ℹ️ <b>Siz hali o'z guruhingizni tanlamagansiz.</b>\n\n"
            "Dars jadvalini ko'rish uchun avval universitet va guruhingizni biriktiring.",
            parse_mode="HTML",
            reply_markup=get_mini_app_inline_button(),
        )
        return

    await message.answer(
        "📆 Ertangi darslar ro'yxati yuklanmoqda...",
        parse_mode="HTML",
    )


@router.message(F.text == "📅 Dars jadvalim")
async def handle_my_schedule(message: Message, current_user: User):
    await message.answer(
        "📅 <b>Haftalik dars jadvalingiz</b>ni to'liq va qulay ko'rinishda ko'rish uchun "
        "Telegram Mini App'dan foydalanishingiz mumkin:",
        parse_mode="HTML",
        reply_markup=get_mini_app_inline_button("📱 Jadvalni Mini Appda ochish"),
    )


@router.message(F.text == "📤 Jadval yuborish")
async def handle_send_schedule_prompt(message: Message, current_user: User):
    await message.answer(
        "📸 <b>Dars jadvali screenshotini yuborish</b>\n\n"
        "Universitetingiz dars jadvali rasmini (screenshot) botga rasm holatida yuboring.\n"
        "Sun'iy intellekt (AI) jadvalingizni avtomatik tahlil qilib, tizimga kiritadi va "
        "admin tekshiruvidan so'ng faollashtiradi.",
        parse_mode="HTML",
    )


@router.message(F.text == "📊 Jadval holati")
async def handle_schedule_status(message: Message, current_user: User):
    await message.answer(
        "📊 <b>Dars jadvali holati:</b>\n\n"
        "Hozirda siz yuborgan tasdiqlash kutilayotgan screenshotlar mavjud emas.\n"
        "Yangi jadval yuklash uchun <b>📤 Jadval yuborish</b> tugmasini bosing.",
        parse_mode="HTML",
    )


@router.message(F.text == "⚙️ Sozlamalar")
async def handle_settings(message: Message, current_user: User):
    role_title = "Administrator" if current_user.role.value == "ADMIN" else "Talaba"
    info_text = (
        f"⚙️ <b>Sizning profilingiz va sozlamalar:</b>\n\n"
        f"👤 <b>Ism:</b> {current_user.first_name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{current_user.telegram_id}</code>\n"
        f"🔰 <b>Rol:</b> {role_title}\n"
        f"🌐 <b>Til:</b> {current_user.language_code}\n\n"
        f"Barcha kengaytirilgan sozlamalar va eslatmalarni boshqarish Mini App orqali amalga oshiriladi."
    )
    await message.answer(
        info_text,
        parse_mode="HTML",
        reply_markup=get_mini_app_inline_button("⚙️ Profilni Mini Appda sozlash"),
    )
