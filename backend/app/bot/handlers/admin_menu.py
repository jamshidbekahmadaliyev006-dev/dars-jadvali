import asyncio
import json
from datetime import datetime
from typing import Optional
import pytz
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, KeyboardButton, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.bot.keyboards.inline import admin_review_keyboard, announcement_confirm_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import AnnouncementStates
from app.bot.text_utils import esc
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import NotificationType, SubmissionStatus, UserRole
from app.models.log import Announcement, NotificationLog
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Group
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionReview
from app.services.schedule_service import ScheduleService, normalize_subject_name
from app.services.user_service import UserService

router = Router(name="admin_menu")

ADMIN_ONLY_TEXT = "⚠️ Bu bo'lim faqat tizim administratorlari uchun."


def is_admin_check(current_user: User) -> bool:
    return current_user.role == UserRole.ADMIN


@router.message(F.text == "🎓 Talaba ko'rinishiga o'tish")
async def handle_switch_to_student_view(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    kb = get_user_main_keyboard()
    kb.keyboard.append([KeyboardButton(text="🛠 Admin paneliga qaytish")])
    await message.answer("🎓 Talaba menyusi ochildi.", reply_markup=kb)


@router.message(F.text == "🛠 Admin paneliga qaytish")
async def handle_switch_back_to_admin(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    await message.answer("🛠 Admin menyusi ochildi.", reply_markup=get_admin_main_keyboard())


@router.message(F.text == "📈 Statistika")
async def handle_admin_statistics(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        await message.answer(ADMIN_ONLY_TEXT)
        return

    total_users = await session.scalar(select(func.count(User.id))) or 0
    users_with_group = await session.scalar(select(func.count(User.id)).where(User.group_id.is_not(None))) or 0
    total_groups = await session.scalar(select(func.count(Group.id))) or 0
    groups_with_schedule = await session.scalar(
        select(func.count(func.distinct(Schedule.group_id))).where(Schedule.is_active == True)
    ) or 0
    total_lessons = await session.scalar(select(func.count(Schedule.id)).where(Schedule.is_active == True)) or 0
    pending = await session.scalar(
        select(func.count(ScheduleSubmission.id)).where(ScheduleSubmission.status == SubmissionStatus.ADMIN_REVIEW)
    ) or 0

    # created_at UTC'da saqlanadi, kun esa mahalliy vaqt bo'yicha hisoblanadi
    tz = pytz.timezone(settings.TIMEZONE)
    today_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
    reminder_filter = (
        NotificationLog.notification_type == NotificationType.LESSON_REMINDER,
        NotificationLog.created_at >= today_start,
    )
    sent_today = await session.scalar(
        select(func.count(NotificationLog.id)).where(*reminder_filter, NotificationLog.is_success == True)
    ) or 0
    failed_today = await session.scalar(
        select(func.count(NotificationLog.id)).where(*reminder_filter, NotificationLog.is_success == False)
    ) or 0

    await message.answer(
        f"📈 <b>Statistika</b>\n\n"
        f"👤 Talabalar: {total_users} ta ({users_with_group} tasi guruhga ulangan)\n"
        f"👥 Guruhlar: {total_groups} ta ({groups_with_schedule} tasida jadval bor)\n"
        f"📚 Faol darslar: {total_lessons} ta\n"
        f"📥 Tekshiruv kutmoqda: {pending} ta\n"
        f"⏰ Bugungi eslatmalar: {sent_today} ta yuborildi, {failed_today} ta xato",
        parse_mode="HTML",
    )


def _submission_caption(submission: ScheduleSubmission, student: Optional[User], group: Optional[Group], remaining: int) -> str:
    lessons = []
    if submission.ai_extracted_json:
        try:
            lessons = json.loads(submission.ai_extracted_json)
        except Exception:
            pass
    names = sorted({normalize_subject_name(item.get("subject") or "")[0] for item in lessons})
    numbered = "\n".join(f"{i}. {esc(name)}" for i, name in enumerate(names, start=1))

    lines = [f"📥 <b>Jadval #{submission.id}</b> (navbatda: {remaining} ta)\n"]
    if student:
        lines.append(f"👤 {esc(student.first_name)}")
    if group:
        lines.append(f"👥 {esc(group.name)}")
    lines.append(f"📚 {len(names)} ta fan · {len(lessons)} ta dars")
    if numbered:
        lines.append(f"\n{numbered}")
    # Telegram rasm izohi 1024 belgidan oshmasligi kerak
    return "\n".join(lines)[:1000]


async def _send_next_submission(message: Message, session: AsyncSession) -> bool:
    subs = await ScheduleService.list_submissions(session, status=SubmissionStatus.ADMIN_REVIEW)
    if not subs:
        return False

    sub = subs[-1]  # eng eskisi birinchi ko'rib chiqiladi
    student = await UserService.get_by_id(session, sub.user_id)
    group = await session.get(Group, sub.group_id) if sub.group_id else None
    caption = _submission_caption(sub, student, group, len(subs))
    keyboard = admin_review_keyboard(sub.id)

    try:
        await message.answer_photo(sub.image_file_id, caption=caption, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        # API orqali yuklangan rasmlarning Telegram file_id'si yo'q
        logger.warning(f"Submission {sub.id} photo unavailable: {e}")
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)
    return True


@router.message(F.text == "📥 Yangi screenshotlar")
async def handle_admin_screenshots(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    if not await _send_next_submission(message, session):
        await message.answer("✅ Tekshiruv kutayotgan jadval yo'q.")


async def _finish_review(query: CallbackQuery, text: str) -> None:
    """Tugmalarni olib, natijani yozadi; rasmli xabarda matn o'rniga izoh tahrirlanadi"""
    if query.message.photo:
        await query.message.edit_caption(caption=text, parse_mode="HTML")
    else:
        await query.message.edit_text(text, parse_mode="HTML")


async def _notify_student(query: CallbackQuery, session: AsyncSession, user_id: int, text: str) -> None:
    student = await UserService.get_by_id(session, user_id)
    if not student:
        return
    try:
        await query.bot.send_message(chat_id=student.telegram_id, text=text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Failed to notify student {student.telegram_id}: {e}")


async def _review(query: CallbackQuery, current_user: User, session: AsyncSession, status: SubmissionStatus) -> None:
    if not is_admin_check(current_user):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return

    sub_id = int(query.data.split("_")[-1])
    submission = await ScheduleService.get_submission_by_id(session, sub_id)
    if not submission:
        await query.answer("Jadval topilmadi", show_alert=True)
        return
    if submission.status != SubmissionStatus.ADMIN_REVIEW:
        await query.answer("Bu jadval allaqachon ko'rib chiqilgan", show_alert=True)
        return

    approved = status == SubmissionStatus.APPROVED
    review = ScheduleSubmissionReview(
        status=status,
        admin_notes="Telegram bot orqali tasdiqlandi" if approved else "Telegram bot orqali rad etildi",
    )
    updated = await ScheduleService.review_submission(session, sub_id, current_user.id, review)

    warning = updated.admin_notes if updated.admin_notes and "⚠️" in updated.admin_notes else None
    if approved:
        result = f"✅ <b>Jadval #{sub_id} tasdiqlandi</b>"
        student_text = "✅ <b>Jadvalingiz tasdiqlandi</b>\n\nGuruh jadvali yangilandi."
    else:
        result = f"❌ <b>Jadval #{sub_id} rad etildi</b>"
        student_text = "❌ <b>Jadvalingiz rad etildi</b>\n\nAniqroq rasm yuborib ko'ring."
    if warning:
        result = f"{result}\n\n{esc(warning)}"

    await _finish_review(query, result)
    await query.answer()
    if not warning:
        await _notify_student(query, session, submission.user_id, student_text)
    await _send_next_submission(query.message, session)


@router.callback_query(F.data.startswith("approve_sub_"))
async def handle_approve_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    await _review(query, current_user, session, SubmissionStatus.APPROVED)


@router.callback_query(F.data.startswith("reject_sub_"))
async def handle_reject_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    await _review(query, current_user, session, SubmissionStatus.REJECTED)


@router.message(F.text == "👥 Guruhlar")
async def handle_admin_groups(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return

    groups = (await session.execute(
        select(Group).options(selectinload(Group.university)).order_by(Group.id.desc()).limit(20)
    )).scalars().all()
    if not groups:
        await message.answer("👥 Hali guruh yo'q.")
        return

    students = dict((await session.execute(
        select(User.group_id, func.count(User.id)).group_by(User.group_id)
    )).all())
    lessons = dict((await session.execute(
        select(Schedule.group_id, func.count(Schedule.id)).where(Schedule.is_active == True).group_by(Schedule.group_id)
    )).all())

    lines = ["👥 <b>Guruhlar</b>\n"]
    for g in groups:
        icon = "✅" if lessons.get(g.id) else "⚪️"
        university = g.university.short_name or g.university.name if g.university else ""
        lines.append(
            f"{icon} <b>{esc(g.name)}</b> — {esc(university)}\n"
            f"     {students.get(g.id, 0)} talaba · {lessons.get(g.id, 0)} dars"
        )
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "👤 Foydalanuvchilar")
async def handle_admin_users(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return

    total = await session.scalar(select(func.count(User.id))) or 0
    users = (await session.execute(
        select(User).options(selectinload(User.group)).order_by(User.id.desc()).limit(15)
    )).scalars().all()

    lines = [f"👤 <b>Foydalanuvchilar</b>: {total} ta\n"]
    for u in users:
        icon = "👑" if u.role == UserRole.ADMIN else "🎓"
        username = f" @{esc(u.username)}" if u.username else ""
        group = esc(u.group.name) if u.group else "guruhsiz"
        lines.append(f"{icon} {esc(u.first_name)}{username} — {group}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _announcement_recipients(session: AsyncSession, university_id: int) -> list:
    stmt = select(User).where(User.university_id == university_id, User.is_active == True)
    return list((await session.execute(stmt)).scalars().all())


@router.message(F.text == "📢 E'lon yuborish")
async def handle_announcement_prompt(message: Message, current_user: User, state: FSMContext):
    if not is_admin_check(current_user):
        return
    if not current_user.university_id:
        await message.answer("❗ Avval /register orqali universitetingizni tanlang.")
        return
    await state.set_state(AnnouncementStates.waiting_text)
    await message.answer("📢 E'lon matnini yozing. U universitetingiz talabalariga yuboriladi.")


@router.callback_query(F.data == "announce_cancel")
async def handle_announcement_cancel(query: CallbackQuery, current_user: User, state: FSMContext):
    if not is_admin_check(current_user):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return
    await state.clear()
    await query.message.edit_text("❌ E'lon bekor qilindi.")
    await query.answer()


@router.callback_query(F.data == "announce_send")
async def handle_announcement_send(query: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    if not is_admin_check(current_user):
        await query.answer("Ruxsat berilmagan!", show_alert=True)
        return

    text = (await state.get_data()).get("announcement_text")
    await state.clear()
    if not text or not current_user.university_id:
        await query.answer("E'lon topilmadi, qaytadan yozing", show_alert=True)
        return

    await query.message.edit_text("⏳ E'lon yuborilmoqda...")
    await query.answer()

    session.add(Announcement(
        university_id=current_user.university_id,
        title=text[:100],
        content=text,
    ))
    await session.commit()

    sent = failed = 0
    for student in await _announcement_recipients(session, current_user.university_id):
        try:
            await query.bot.send_message(
                chat_id=student.telegram_id,
                text=f"📢 <b>E'lon</b>\n\n{esc(text)}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Announcement not delivered to {student.telegram_id}: {e}")
        await asyncio.sleep(0.05)  # Telegram tezlik chegarasi: sekundiga ~30 xabar

    await query.message.edit_text(f"✅ E'lon yuborildi: {sent} ta. Yetib bormadi: {failed} ta.")


# Bu handler oxirida turadi: menyu tugmalari e'lon matni bo'lib qolmasligi uchun
@router.message(AnnouncementStates.waiting_text, F.text)
async def handle_announcement_text(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not is_admin_check(current_user):
        await state.clear()
        return

    text = (message.text or "").strip()
    recipients = await _announcement_recipients(session, current_user.university_id)
    await state.update_data(announcement_text=text)
    await message.answer(
        f"📢 <b>Tekshiring</b>\n\n{esc(text)}\n\n<i>{len(recipients)} ta talabaga yuboriladi.</i>",
        parse_mode="HTML",
        reply_markup=announcement_confirm_keyboard(),
    )
