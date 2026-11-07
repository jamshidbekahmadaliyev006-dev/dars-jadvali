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
from app.bot.i18n import format_counts, labels, lang_of, t
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


def is_admin_check(current_user: User) -> bool:
    return current_user.role == UserRole.ADMIN


@router.message(F.text.in_(labels("btn_student_view")))
async def handle_switch_to_student_view(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)
    kb = get_user_main_keyboard(lang)
    kb.keyboard.append([KeyboardButton(text=t(lang, "btn_admin_back"))])
    await message.answer(t(lang, "admin_student_menu"), reply_markup=kb)


@router.message(F.text.in_(labels("btn_admin_back")))
async def handle_switch_back_to_admin(message: Message, current_user: User):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)
    await message.answer(t(lang, "admin_menu_opened"), reply_markup=get_admin_main_keyboard(lang))


@router.message(F.text.in_(labels("btn_stats")))
async def handle_admin_statistics(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await message.answer(t(lang, "admin_only"))
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
        t(
            lang,
            "stats",
            users=total_users,
            linked=users_with_group,
            groups=total_groups,
            with_schedule=groups_with_schedule,
            lessons=total_lessons,
            pending=pending,
            sent=sent_today,
            failed=failed_today,
        ),
        parse_mode="HTML",
    )


def _submission_caption(
    submission: ScheduleSubmission,
    student: Optional[User],
    group: Optional[Group],
    remaining: int,
    lang: str,
) -> str:
    lessons = []
    if submission.ai_extracted_json:
        try:
            lessons = json.loads(submission.ai_extracted_json)
        except Exception:
            pass
    names = sorted({normalize_subject_name(item.get("subject") or "")[0] for item in lessons})
    numbered = "\n".join(f"{i}. {esc(name)}" for i, name in enumerate(names, start=1))

    lines = [t(lang, "review_title", id=submission.id, left=remaining)]
    if student:
        lines.append(f"👤 {esc(student.first_name)}")
    if group:
        lines.append(f"👥 {esc(group.name)}")
    lines.append(f"📚 {format_counts(len(names), len(lessons), lang)}")
    if numbered:
        lines.append(f"\n{numbered}")
    # Telegram rasm izohi 1024 belgidan oshmasligi kerak
    return "\n".join(lines)[:1000]


async def _send_next_submission(message: Message, session: AsyncSession, lang: str) -> bool:
    subs = await ScheduleService.list_submissions(session, status=SubmissionStatus.ADMIN_REVIEW)
    if not subs:
        return False

    sub = subs[-1]  # eng eskisi birinchi ko'rib chiqiladi
    student = await UserService.get_by_id(session, sub.user_id)
    group = await session.get(Group, sub.group_id) if sub.group_id else None
    caption = _submission_caption(sub, student, group, len(subs), lang)
    keyboard = admin_review_keyboard(sub.id, lang)

    try:
        await message.answer_photo(sub.image_file_id, caption=caption, parse_mode="HTML", reply_markup=keyboard)
    except Exception as e:
        # API orqali yuklangan rasmlarning Telegram file_id'si yo'q
        logger.warning(f"Submission {sub.id} photo unavailable: {e}")
        await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)
    return True


@router.message(F.text.in_(labels("btn_new_shots")))
async def handle_admin_screenshots(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)
    if not await _send_next_submission(message, session, lang):
        await message.answer(t(lang, "review_empty"))


async def _finish_review(query: CallbackQuery, text: str) -> None:
    """Tugmalarni olib, natijani yozadi; rasmli xabarda matn o'rniga izoh tahrirlanadi"""
    if query.message.photo:
        await query.message.edit_caption(caption=text, parse_mode="HTML")
    else:
        await query.message.edit_text(text, parse_mode="HTML")


async def _notify_student(query: CallbackQuery, session: AsyncSession, user_id: int, text_key: str) -> None:
    student = await UserService.get_by_id(session, user_id)
    if not student:
        return
    try:
        await query.bot.send_message(
            chat_id=student.telegram_id,
            text=t(lang_of(student), text_key),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Failed to notify student {student.telegram_id}: {e}")


async def _review(query: CallbackQuery, current_user: User, session: AsyncSession, status: SubmissionStatus) -> None:
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "no_permission"), show_alert=True)
        return

    sub_id = int(query.data.split("_")[-1])
    submission = await ScheduleService.get_submission_by_id(session, sub_id)
    if not submission:
        await query.answer(t(lang, "review_missing"), show_alert=True)
        return
    if submission.status != SubmissionStatus.ADMIN_REVIEW:
        await query.answer(t(lang, "review_done_before"), show_alert=True)
        return

    approved = status == SubmissionStatus.APPROVED
    review = ScheduleSubmissionReview(
        status=status,
        admin_notes="Telegram bot orqali tasdiqlandi" if approved else "Telegram bot orqali rad etildi",
    )
    updated = await ScheduleService.review_submission(session, sub_id, current_user.id, review)

    warning = updated.admin_notes if updated.admin_notes and "⚠️" in updated.admin_notes else None
    result = t(lang, "review_approved" if approved else "review_rejected", id=sub_id)
    if warning:
        result = f"{result}\n\n{esc(warning)}"

    await _finish_review(query, result)
    await query.answer()
    if not warning:
        await _notify_student(query, session, submission.user_id, "student_approved" if approved else "student_rejected")
    await _send_next_submission(query.message, session, lang)


@router.callback_query(F.data.startswith("approve_sub_"))
async def handle_approve_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    await _review(query, current_user, session, SubmissionStatus.APPROVED)


@router.callback_query(F.data.startswith("reject_sub_"))
async def handle_reject_submission_callback(query: CallbackQuery, current_user: User, session: AsyncSession):
    await _review(query, current_user, session, SubmissionStatus.REJECTED)


@router.message(F.text.in_(labels("btn_groups")))
async def handle_admin_groups(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)

    groups = (await session.execute(
        select(Group).options(selectinload(Group.university)).order_by(Group.id.desc()).limit(20)
    )).scalars().all()
    if not groups:
        await message.answer(t(lang, "groups_empty"))
        return

    students = dict((await session.execute(
        select(User.group_id, func.count(User.id)).group_by(User.group_id)
    )).all())
    lessons = dict((await session.execute(
        select(Schedule.group_id, func.count(Schedule.id)).where(Schedule.is_active == True).group_by(Schedule.group_id)
    )).all())

    lines = [t(lang, "groups_title")]
    for g in groups:
        icon = "✅" if lessons.get(g.id) else "⚪️"
        university = g.university.short_name or g.university.name if g.university else ""
        counts = t(lang, "group_counts", students=students.get(g.id, 0), lessons=lessons.get(g.id, 0))
        lines.append(f"{icon} <b>{esc(g.name)}</b> — {esc(university)}\n     {counts}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text.in_(labels("btn_users")))
async def handle_admin_users(message: Message, current_user: User, session: AsyncSession):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)

    total = await session.scalar(select(func.count(User.id))) or 0
    users = (await session.execute(
        select(User).options(selectinload(User.group)).order_by(User.id.desc()).limit(15)
    )).scalars().all()

    lines = [t(lang, "users_title", total=total)]
    for u in users:
        icon = "👑" if u.role == UserRole.ADMIN else "🎓"
        username = f" @{esc(u.username)}" if u.username else ""
        group = esc(u.group.name) if u.group else t(lang, "no_group")
        lines.append(f"{icon} {esc(u.first_name)}{username} — {group}")
    await message.answer("\n".join(lines), parse_mode="HTML")


async def _announcement_recipients(session: AsyncSession, university_id: int) -> list:
    stmt = select(User).where(User.university_id == university_id, User.is_active == True)
    return list((await session.execute(stmt)).scalars().all())


@router.message(F.text.in_(labels("btn_announce")))
async def handle_announcement_prompt(message: Message, current_user: User, state: FSMContext):
    if not is_admin_check(current_user):
        return
    lang = lang_of(current_user)
    if not current_user.university_id:
        await message.answer(t(lang, "announce_need_university"))
        return
    await state.set_state(AnnouncementStates.waiting_text)
    await message.answer(t(lang, "announce_prompt"))


@router.callback_query(F.data == "announce_cancel")
async def handle_announcement_cancel(query: CallbackQuery, current_user: User, state: FSMContext):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "no_permission"), show_alert=True)
        return
    await state.clear()
    await query.message.edit_text(t(lang, "announce_cancelled"))
    await query.answer()


@router.callback_query(F.data == "announce_send")
async def handle_announcement_send(query: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "no_permission"), show_alert=True)
        return

    text = (await state.get_data()).get("announcement_text")
    await state.clear()
    if not text or not current_user.university_id:
        await query.answer(t(lang, "announce_missing"), show_alert=True)
        return

    await query.message.edit_text(t(lang, "announce_sending"))
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
                text=t(lang_of(student), "announce_header", text=esc(text)),
                parse_mode="HTML",
            )
            sent += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Announcement not delivered to {student.telegram_id}: {e}")
        await asyncio.sleep(0.05)  # Telegram tezlik chegarasi: sekundiga ~30 xabar

    await query.message.edit_text(t(lang, "announce_done", sent=sent, failed=failed))


# Bu handler oxirida turadi: menyu tugmalari e'lon matni bo'lib qolmasligi uchun
@router.message(AnnouncementStates.waiting_text, F.text)
async def handle_announcement_text(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not is_admin_check(current_user):
        await state.clear()
        return

    lang = lang_of(current_user)
    text = (message.text or "").strip()
    recipients = await _announcement_recipients(session, current_user.university_id)
    await state.update_data(announcement_text=text)
    await message.answer(
        t(lang, "announce_preview", text=esc(text), count=len(recipients)),
        parse_mode="HTML",
        reply_markup=announcement_confirm_keyboard(lang),
    )
