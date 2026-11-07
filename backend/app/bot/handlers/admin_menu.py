from aiogram import F, Router
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.models.enums import UserRole
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, University
from app.models.user import User

router = Router(name="admin_menu")


def is_admin_check(current_user: User) -> bool:
    return current_user.role == UserRole.ADMIN


@router.message(F.text == "🎓 Talaba ko'rinishiga o'tish")
async def handle_switch_to_student_view(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    kb = get_user_main_keyboard()
    # Qo'shimcha ravishda admin paneliga qaytish tugmasini qo'shish
    kb.keyboard.append([KeyboardButton(text="🛠 Admin paneliga qaytish")])
    await message.answer(
        "🎓 <b>Talaba ko'rinishiga o'tildi.</b>\nTalabalar botni qanday ko'rishini sinab ko'rishingiz mumkin.",
        parse_mode="HTML",
        reply_markup=kb,
    )


@router.message(F.text == "🛠 Admin paneliga qaytish")
async def handle_switch_back_to_admin(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "👑 <b>Admin boshqaruv paneliga qaytildi.</b>",
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard(),
    )


@router.message(F.text == "📈 Statistika")
async def handle_admin_statistics(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        await message.answer("⚠️ Ushbu bo'lim faqat tizim administratorlari uchun mo'ljallangan.")
        return

    # Statistika hisoblash
    total_users = await session.scalar(select(func.count(User.id))) or 0
    total_universities = await session.scalar(select(func.count(University.id))) or 0
    total_faculties = await session.scalar(select(func.count(Faculty.id))) or 0
    total_groups = await session.scalar(select(func.count(Group.id))) or 0
    total_schedules = await session.scalar(select(func.count(Schedule.id))) or 0
    pending_submissions = await session.scalar(
        select(func.count(ScheduleSubmission.id)).where(ScheduleSubmission.status == "PENDING")
    ) or 0

    stats_text = (
        f"📊 <b>UniNotify Tizim Statistikasi:</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {total_users} ta\n"
        f"🏛 <b>Universitetlar:</b> {total_universities} ta\n"
        f"🏢 <b>Fakultetlar:</b> {total_faculties} ta\n"
        f"👥 <b>Guruhlar:</b> {total_groups} ta\n"
        f"🗓 <b>Faol darslar:</b> {total_schedules} ta\n"
        f"📥 <b>Kutilayotgan screenshotlar:</b> {pending_submissions} ta\n"
    )
    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.text == "📥 Yangi screenshotlar")
async def handle_admin_screenshots(message: Message, current_user: User):
    if not is_admin_check(current_user):
        await message.answer("⚠️ Ushbu bo'lim faqat administratorlar uchun.")
        return
    await message.answer(
        "📥 <b>Screenshotlar navbati:</b>\n\nHozirda yangi ko'rib chiqilishi kerak bo'lgan jadval screenshotlari mavjud emas.",
        parse_mode="HTML",
    )


@router.message(F.text == "🏛 Universitetlar")
async def handle_admin_universities(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "🏛 <b>Universitetlar boshqaruvi:</b>\n\nUniversitetlarni qo'shish va tahrirlash keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "🏢 Fakultetlar")
async def handle_admin_faculties(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "🏢 <b>Fakultetlar boshqaruvi:</b>\n\nFakultetlarni boshqarish keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "👥 Guruhlar")
async def handle_admin_groups(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "👥 <b>Guruhlar boshqaruvi:</b>\n\nGuruhlarni boshqarish keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "🚪 Binolar va xonalar")
async def handle_admin_rooms(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "🚪 <b>Binolar va auditoriyalar:</b>\n\nAuditoriyalarni boshqarish keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "👤 Foydalanuvchilar")
async def handle_admin_users(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    users = await UserService.list_users(session, limit=10)
    lines = ["👤 <b>Oxirgi foydalanuvchilar:</b>\n"]
    for u in users:
        role_icon = "👑" if u.role == UserRole.ADMIN else "🎓"
        lines.append(f"{role_icon} {u.first_name} (@{u.username or 'yo‘q'}) — ID: <code>{u.telegram_id}</code> [{u.role.value}]")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📢 E’lonlar")
async def handle_admin_announcements(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "📢 <b>Universitet e'lonlari:</b>\n\nE'lon yaratish va tarqatish keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "🗓 Dars jadvallari")
async def handle_admin_schedules(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer(
        "🗓 <b>Dars jadvallari ro'yxati:</b>\n\nJadvallarni tahrirlash va tasdiqlash keyingi bosqichda faollashadi.",
        parse_mode="HTML",
    )
