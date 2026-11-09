import asyncio
import json
from datetime import datetime
from typing import Optional
import pytz
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.bot.album import send_submission_files, unpack_file_ids
from app.bot.i18n import NL, format_counts, labels, lang_of, t
from app.bot.keyboards.inline import admin_review_keyboard, announcement_confirm_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import AnnouncementStates
from app.bot.text_utils import esc
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import NotificationType, SubmissionStatus, TeacherStatus, UserRole
from app.models.log import Announcement, NotificationLog
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionReview
from app.services.schedule_service import ScheduleService, normalize_subject_name
from app.services.university_service import GENERAL_FACULTY_NAME, name_key
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


async def collect_statistics(session: AsyncSession) -> dict:
    """Universitet, fakultet, o'qituvchi, guruh va takrorlanmas fanlar soni"""
    universities = await session.scalar(select(func.count(University.id))) or 0
    faculties = await session.scalar(
        select(func.count(Faculty.id)).where(Faculty.name != GENERAL_FACULTY_NAME)
    ) or 0
    teachers = await session.scalar(
        select(func.count(TeacherProfile.id)).where(TeacherProfile.status == TeacherStatus.APPROVED)
    ) or 0
    groups = await session.scalar(select(func.count(Group.id))) or 0

    # Fanlar: guruhlardagi darslar emas, har bir fan bitta. "Matematika (4 kr)-MAT001", "matematika"
    # va o'qituvchi jadvalidagi "Matematika" - hammasi bitta fan sifatida sanaladi.
    names = (await session.execute(
        select(Subject.name).join(Schedule, Schedule.subject_id == Subject.id).where(Schedule.is_active == True)
    )).scalars().all()
    names += (await session.execute(
        select(TeacherLesson.subject).where(TeacherLesson.is_active == True)
    )).scalars().all()
    subjects = len({name_key(normalize_subject_name(n)[0]) for n in names if n and name_key(n)})

    return {"universities": universities, "faculties": faculties, "teachers": teachers, "groups": groups, "subjects": subjects}


async def collect_user_counts(session: AsyncSession) -> dict:
    """
    Har bir foydalanuvchi aniq BITTA toifaga tushadi, shuning uchun toifalar yig'indisi = jami:
    tasdiqlangan o'qituvchi > tasdiq kutayotgan o'qituvchi > talaba (guruhi bor) > ro'yxatdan o'tmagan.
    """
    total = await session.scalar(select(func.count(User.id))) or 0
    approved_ids = select(TeacherProfile.user_id).where(TeacherProfile.status == TeacherStatus.APPROVED)
    pending_ids = select(TeacherProfile.user_id).where(TeacherProfile.status == TeacherStatus.PENDING)
    teachers = await session.scalar(select(func.count(User.id)).where(User.id.in_(approved_ids))) or 0
    pending = await session.scalar(
        select(func.count(User.id)).where(User.id.in_(pending_ids), User.id.not_in(approved_ids))
    ) or 0
    students = await session.scalar(
        select(func.count(User.id)).where(
            User.group_id.is_not(None), User.id.not_in(approved_ids), User.id.not_in(pending_ids)
        )
    ) or 0
    unregistered = total - teachers - pending - students
    return {"total": total, "teachers": teachers, "pending": pending, "students": students, "unregistered": unregistered}


async def _users_message(session: AsyncSession, lang: str) -> str:
    c = await collect_user_counts(session)
    text = t(lang, "users_stats", total=c["total"], teachers=c["teachers"], students=c["students"])
    if c["pending"]:
        text += NL + t(lang, "users_pending", n=c["pending"])
    text += NL + t(lang, "users_unregistered", n=c["unregistered"])
    return text


def _live_footer(lang: str) -> str:
    now = datetime.now(pytz.timezone(settings.TIMEZONE))
    return NL + NL + t(lang, "live_at", time=now.strftime("%d.%m.%Y %H:%M:%S"))


def _refresh_kb(lang: str, data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t(lang, "btn_refresh"), callback_data=data)]])


async def _stats_text(session: AsyncSession, lang: str) -> str:
    return t(lang, "stats", **await collect_statistics(session)) + _live_footer(lang)


async def _users_text(session: AsyncSession, lang: str) -> str:
    return await _users_message(session, lang) + _live_footer(lang)


@router.message(F.text.in_(labels("btn_stats")))
async def handle_admin_statistics(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await message.answer(t(lang, "admin_only"))
        return
    # Har safar bazadan qaytadan hisoblanadi - kesh yo'q
    await message.answer(await _stats_text(session, lang), parse_mode="HTML", reply_markup=_refresh_kb(lang, "adm_refresh_stats"))


@router.callback_query(F.data.in_({"adm_refresh_stats", "adm_refresh_users"}))
async def handle_admin_refresh(query: CallbackQuery, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "admin_only"), show_alert=True)
        return
    await query.answer()
    text = await (_stats_text if query.data == "adm_refresh_stats" else _users_text)(session, lang)
    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=_refresh_kb(lang, query.data))
    except Exception:
        pass


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

    file_ids = unpack_file_ids(sub.image_url, sub.image_file_id)
    try:
        if len(file_ids) > 1:
            await send_submission_files(message.bot, message.chat.id, file_ids, caption, as_document=False)
            await message.answer(
                t(lang, "review_buttons", id=sub.id, n=len(file_ids)), parse_mode="HTML", reply_markup=keyboard
            )
        else:
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
        if approved and submission.group_id:
            await _notify_group_updated(query, session, submission.group_id, exclude_user_id=submission.user_id)
    await _send_next_submission(query.message, session, lang)


async def _notify_group_updated(query: CallbackQuery, session: AsyncSession, group_id: int, exclude_user_id: int) -> None:
    """Admin tasdiqlagan yangi jadval haqida guruhning qolgan a'zolariga xabar"""
    group = await session.get(Group, group_id)
    members = (await session.execute(
        select(User).where(User.group_id == group_id, User.is_active == True, User.id != exclude_user_id)
    )).scalars().all()
    for member in members:
        try:
            await query.bot.send_message(
                member.telegram_id,
                t(lang_of(member), "group_schedule_updated", group=esc(group.name if group else "")),
                parse_mode="HTML",
            )
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Group update notice not delivered to {member.telegram_id}: {type(e).__name__}")


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
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await message.answer(t(lang, "admin_only"))
        return
    await message.answer(await _users_text(session, lang), parse_mode="HTML", reply_markup=_refresh_kb(lang, "adm_refresh_users"))


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
