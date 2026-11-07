from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.models.enums import SubmissionStatus, UserRole
from app.models.log import Announcement
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, University
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionReview
from app.services.schedule_service import ScheduleService
from app.services.university_service import UniversityService
from app.services.user_service import UserService

router = Router(name="admin_menu")


def is_admin_check(current_user: User) -> bool:
    return current_user.role == UserRole.ADMIN


@router.message(F.text == "🎓 Talaba ko'rinishiga o'tish")
async def handle_switch_to_student_view(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    kb = get_user_main_keyboard()
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

    total_users = await session.scalar(select(func.count(User.id))) or 0
    total_universities = await session.scalar(select(func.count(University.id))) or 0
    total_faculties = await session.scalar(select(func.count(Faculty.id))) or 0
    total_groups = await session.scalar(select(func.count(Group.id))) or 0
    total_schedules = await session.scalar(select(func.count(Schedule.id))) or 0
    pending_submissions = await session.scalar(
        select(func.count(ScheduleSubmission.id)).where(ScheduleSubmission.status.in_([SubmissionStatus.PENDING, SubmissionStatus.ADMIN_REVIEW]))
    ) or 0

    stats_text = (
        f"📊 <b>UniNotify Tizim Statistikasi:</b>\n\n"
        f"👥 <b>Foydalanuvchilar:</b> {total_users} ta\n"
        f"🏛 <b>Universitetlar:</b> {total_universities} ta\n"
        f"🏢 <b>Fakultetlar:</b> {total_faculties} ta\n"
        f"👥 <b>Guruhlar:</b> {total_groups} ta\n"
        f"🗓 <b>Faol darslar:</b> {total_schedules} ta\n"
        f"📥 <b>Ko'rib chiqilishi kerak:</b> {pending_submissions} ta screenshot\n"
    )
    await message.answer(stats_text, parse_mode="HTML")


@router.message(F.text == "📥 Yangi screenshotlar")
async def handle_admin_screenshots(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return

    subs = await ScheduleService.list_submissions(session, status=SubmissionStatus.ADMIN_REVIEW)
    if not subs:
        subs = await ScheduleService.list_submissions(session, status=SubmissionStatus.PENDING)

    if not subs:
        await message.answer("✅ <b>Yangi ko'rib chiqilishi kerak bo'lgan screenshotlar mavjud emas.</b>", parse_mode="HTML")
        return

    sub = subs[0]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_sub_{sub.id}"),
                InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_sub_{sub.id}"),
            ]
        ]
    )

    info_text = (
        f"📥 <b>Yangi Jadval Arixasi:</b> #{sub.id}\n"
        f"👤 <b>Foydalanuvchi ID:</b> {sub.user_id}\n"
        f"🏛 <b>Universitet ID:</b> {sub.university_id}\n"
        f"📊 <b>Holati:</b> {sub.status.value}\n"
        f"🤖 <b>AI Confidence:</b> {sub.ai_confidence or 'N/A'}\n\n"
        f"<i>Quyidagi tugmalar orqali ushbu jadvalni tasdiqlashingiz yoki rad etishingiz mumkin:</i>"
    )
    await message.answer(info_text, parse_mode="HTML", reply_markup=keyboard)


@router.callback_query(F.data.startswith("approve_sub_"))
async def handle_approve_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return

    sub_id = int(query.data.split("_")[-1])
    review = ScheduleSubmissionReview(status=SubmissionStatus.APPROVED, admin_notes="Telegram bot orqali tasdiqlandi")
    updated = await ScheduleService.review_submission(session, sub_id, current_user.id, review)

    if updated:
        if updated.admin_notes and "⚠️" in updated.admin_notes:
            await query.message.edit_text(
                f"✅ <b>Ariza #{sub_id} tasdiqlandi.</b>\n\n{updated.admin_notes}",
                parse_mode="HTML",
            )
        else:
            await query.message.edit_text(
                f"✅ <b>Ariza #{sub_id} muvaffaqiyatli tasdiqlandi!</b>\n"
                f"AI aniqlagan darslar guruh jadvaliga avtomatik qo'shildi va eslatmalar yoqildi.",
                parse_mode="HTML",
            )
        await query.answer("Tasdiqlandi!")
    else:
        await query.answer("Xatolik yuz berdi!", show_alert=True)


@router.callback_query(F.data.startswith("reject_sub_"))
async def handle_reject_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return

    sub_id = int(query.data.split("_")[-1])
    review = ScheduleSubmissionReview(status=SubmissionStatus.REJECTED, admin_notes="Telegram bot orqali rad etildi")
    updated = await ScheduleService.review_submission(session, sub_id, current_user.id, review)

    if updated:
        await query.message.edit_text(f"❌ <b>Ariza #{sub_id} rad etildi.</b>", parse_mode="HTML")
        await query.answer("Rad etildi!")
    else:
        await query.answer("Xatolik yuz berdi!", show_alert=True)


@router.message(F.text == "🏛 Universitetlar")
async def handle_admin_universities(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    univs = await UniversityService.get_all_universities(session, only_active=False)
    if not univs:
        await message.answer("🏛 <b>Tizimda universitetlar hali mavjud emas.</b>\nAPI orqali qo'shishingiz mumkin.", parse_mode="HTML")
        return
    lines = ["🏛 <b>Mavjud Universitetlar:</b>\n"]
    for u in univs[:10]:
        st = "🟢" if u.is_active else "🔴"
        lines.append(f"{st} <b>{u.name}</b> ({u.short_name or '-'}) [ID: {u.id}]")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "🏢 Fakultetlar")
async def handle_admin_faculties(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    total_faculties = await session.scalar(select(func.count(Faculty.id))) or 0
    await message.answer(f"🏢 <b>Tizimda jami fakultetlar soni:</b> {total_faculties} ta", parse_mode="HTML")


@router.message(F.text == "👥 Guruhlar")
async def handle_admin_groups(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    total_groups = await session.scalar(select(func.count(Group.id))) or 0
    await message.answer(f"👥 <b>Tizimda jami guruhlar soni:</b> {total_groups} ta", parse_mode="HTML")


@router.message(F.text == "🚪 Binolar va xonalar")
async def handle_admin_rooms(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    await message.answer("🚪 <b>Binolar va auditoriyalar:</b> Barcha ma'lumotlar API va Mini App orqali to'liq boshqariladi.", parse_mode="HTML")


@router.message(F.text == "👤 Foydalanuvchilar")
async def handle_admin_users(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    users = await UserService.list_users(session, limit=10)
    lines = ["👤 <b>Oxirgi ro'yxatdan o'tganlar:</b>\n"]
    for u in users:
        role_icon = "👑" if u.role == UserRole.ADMIN else "🎓"
        lines.append(f"{role_icon} {u.first_name} (@{u.username or 'yo‘q'}) — ID: <code>{u.telegram_id}</code> [{u.role.value}]")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📢 E’lonlar")
async def handle_admin_announcements(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    anns = await session.scalars(select(Announcement).order_by(Announcement.id.desc()).limit(5))
    ann_list = list(anns.all())
    if not ann_list:
        await message.answer("📢 <b>Hozircha hech qanday e'lon berilmagan.</b>", parse_mode="HTML")
        return
    lines = ["📢 <b>So'nggi e'lonlar:</b>\n"]
    for a in ann_list:
        lines.append(f"📌 <b>{a.title}</b>\n{a.content[:100]}...\n")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "🗓 Dars jadvallari")
async def handle_admin_schedules(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    total_sched = await session.scalar(select(func.count(Schedule.id))) or 0
    await message.answer(f"🗓 <b>Tizimdagi jami darslar soni:</b> {total_sched} ta", parse_mode="HTML")
