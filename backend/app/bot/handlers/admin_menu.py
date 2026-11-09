import asyncio
import json
from datetime import datetime
from typing import Optional
import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.bot.album import send_submission_files, unpack_file_ids
from app.bot.sender import BLOCKED, FAILED, NOT_STARTED, OK, safe_send
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
    pairs = (await session.execute(
        select(Subject.name, Subject.code).join(Schedule, Schedule.subject_id == Subject.id).where(Schedule.is_active == True)
    )).all()
    keys = {("c:" + code) if code else ("n:" + name_key(normalize_subject_name(name)[0])) for name, code in pairs if name}
    for subject in (await session.execute(
        select(TeacherLesson.subject).where(TeacherLesson.is_active == True)
    )).scalars().all():
        clean, code = normalize_subject_name(subject or "")
        if clean:
            keys.add(("c:" + code) if code else ("n:" + name_key(clean)))
    subjects = len(keys)

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


def _lookalike_groups(lesson_rows) -> dict:
    """Bir-biriga 90%+ o'xshash jadvalli guruhlar: {guruh_id: o'xshash guruh_id} - adashib yuborilgan jadval belgisi"""
    sigs: dict = {}
    for group_id, day, start, subject in lesson_rows:
        sigs.setdefault(group_id, set()).add((day, start, (subject or "").lower()))
    result = {}
    ids = [g for g, sig in sigs.items() if len(sig) >= 3]
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            union = sigs[a] | sigs[b]
            if union and len(sigs[a] & sigs[b]) / len(union) >= 0.9:
                result.setdefault(a, b)
                result.setdefault(b, a)
    return result


async def build_groups_report(session: AsyncSession, lang: str) -> list:
    """Universitet -> fakultet -> guruhlar; har bir universitet alohida xabar (Telegram uzunlik chegarasi uchun)"""
    groups = (await session.execute(select(Group).order_by(Group.name))).scalars().all()
    if not groups:
        return [t(lang, "groups_empty")]
    universities = {u.id: u for u in (await session.execute(select(University))).scalars().all()}
    faculties = {f.id: f for f in (await session.execute(select(Faculty))).scalars().all()}
    students = dict((await session.execute(
        select(User.group_id, func.count(User.id)).where(User.group_id.is_not(None)).group_by(User.group_id)
    )).all())
    lesson_rows = (await session.execute(
        select(Schedule.group_id, Schedule.day_of_week, Schedule.start_time, Subject.name)
        .join(Subject, Subject.id == Schedule.subject_id).where(Schedule.is_active == True)
    )).all()
    lessons = {}
    for gid, *_ in lesson_rows:
        lessons[gid] = lessons.get(gid, 0) + 1
    names = {g.id: g.name for g in groups}
    lookalike = _lookalike_groups([(g, d.value, st, sj) for g, d, st, sj in lesson_rows])

    pages = []
    for univ_id, univ in sorted(universities.items()):
        univ_groups = [g for g in groups if g.university_id == univ_id]
        if not univ_groups:
            continue
        with_schedule = sum(1 for g in univ_groups if lessons.get(g.id))
        fac_count = len({g.faculty_id for g in univ_groups if faculties.get(g.faculty_id) and faculties[g.faculty_id].name != GENERAL_FACULTY_NAME})
        lines = [
            f"🏛 <b>{esc(univ.name)}</b>",
            t(lang, "groups_summary", faculties=fac_count, groups=len(univ_groups), with_schedule=with_schedule),
        ]
        by_faculty: dict = {}
        for g in univ_groups:
            by_faculty.setdefault(g.faculty_id, []).append(g)
        for fac_id, fac_groups in sorted(by_faculty.items(), key=lambda kv: (faculties[kv[0]].name if kv[0] in faculties else "")):
            fname = faculties[fac_id].name if fac_id in faculties else "—"
            done = sum(1 for g in fac_groups if lessons.get(g.id))
            lines.append(NL + f"🎓 <b>{esc(fname)}</b> · {done}/{len(fac_groups)} 📅")
            for g in sorted(fac_groups, key=lambda g: (not lessons.get(g.id), g.name)):  # jadvallilar yuqorida
                has = bool(lessons.get(g.id))
                row = f"{'✅' if has else '⚪️'} {esc(g.name)} — {students.get(g.id, 0)} 👤"
                if has:
                    row += f" · {lessons[g.id]} 📚"
                if g.id in lookalike:
                    row += f" ⚠️ {esc(names.get(lookalike[g.id], ''))}"
                lines.append(row)
        pages.append(NL.join(lines))
    return pages


@router.message(F.text.in_(labels("btn_groups")))
async def handle_admin_groups(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await message.answer(t(lang, "admin_only"))
        return
    pages = await build_groups_report(session, lang)
    for index, page in enumerate(pages):
        footer = (NL + NL + t(lang, "groups_legend")) if index == len(pages) - 1 else ""
        await message.answer((page + footer)[:4000], parse_mode="HTML")


@router.message(F.text.in_(labels("btn_users")))
async def handle_admin_users(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await message.answer(t(lang, "admin_only"))
        return
    await message.answer(await _users_text(session, lang), parse_mode="HTML", reply_markup=_refresh_kb(lang, "adm_refresh_users"))


async def _announcement_recipients(session: AsyncSession, target: str) -> list:
    """target: "all" - barcha faol foydalanuvchilar, "g<id>" - faqat shu guruh a'zolari"""
    stmt = select(User).where(User.is_active == True)
    if target.startswith("g") and target[1:].isdigit():
        stmt = stmt.where(User.group_id == int(target[1:]))
    return list((await session.execute(stmt)).scalars().all())


async def _audience_label(session: AsyncSession, target: str, lang: str) -> str:
    if target.startswith("g") and target[1:].isdigit():
        group = await session.get(Group, int(target[1:]))
        return t(lang, "announce_to_group", group=esc(group.name if group else "?"))
    return t(lang, "announce_to_all")


@router.message(F.text.in_(labels("btn_announce")))
async def handle_announcement_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        return
    await state.clear()
    groups = (await session.execute(select(Group).order_by(Group.name))).scalars().all()
    rows = [[InlineKeyboardButton(text=t(lang, "announce_to_all"), callback_data="ann_to_all")]]
    chunk = []
    for g in groups[:60]:
        chunk.append(InlineKeyboardButton(text=g.name, callback_data=f"ann_to_g{g.id}"))
        if len(chunk) == 3:
            rows.append(chunk)
            chunk = []
    if chunk:
        rows.append(chunk)
    await message.answer(t(lang, "announce_choose"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("ann_to_"))
async def handle_announcement_audience(query: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "no_permission"), show_alert=True)
        return
    target = query.data[len("ann_to_"):]
    recipients = await _announcement_recipients(session, target)
    await state.set_state(AnnouncementStates.waiting_text)
    await state.update_data(announcement_target=target)
    await query.answer()
    await query.message.edit_text(
        t(lang, "announce_prompt_to", audience=await _audience_label(session, target, lang), count=len(recipients)),
        parse_mode="HTML",
    )


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

    data = await state.get_data()
    text = data.get("announcement_text")
    target = data.get("announcement_target", "all")
    await state.clear()
    if not text:
        await query.answer(t(lang, "announce_missing"), show_alert=True)
        return

    await query.message.edit_text(t(lang, "announce_sending"))
    await query.answer()

    univ_id = current_user.university_id
    if target.startswith("g") and target[1:].isdigit():
        group = await session.get(Group, int(target[1:]))
        univ_id = group.university_id if group else univ_id
    if not univ_id:
        univ_id = await session.scalar(select(University.id).order_by(University.id).limit(1))
    if univ_id:
        session.add(Announcement(university_id=univ_id, title=text[:100], content=text))
        await session.commit()

    sent = 0
    problems = {BLOCKED: [], NOT_STARTED: [], FAILED: []}
    recipients = await _announcement_recipients(session, target)
    for student in recipients:
        status, note = await safe_send(
            query.bot, student.telegram_id,
            t(lang_of(student), "announce_header", text=esc(text)), parse_mode="HTML",
        )
        if status == OK:
            sent += 1
        else:
            label = f"@{student.username}" if student.username else esc(student.first_name or str(student.telegram_id))
            problems[status].append(label)
            logger.warning(f"Announcement not delivered to {student.telegram_id}: {status} {note}")
        await asyncio.sleep(0.04)  # Telegram: sekundiga ~30 xabar

    failed = sum(len(v) for v in problems.values())
    report = t(lang, "announce_done", sent=sent, failed=failed)
    for status, key in ((BLOCKED, "announce_fail_blocked"), (NOT_STARTED, "announce_fail_not_started"), (FAILED, "announce_fail_other")):
        if problems[status]:
            names = ", ".join(problems[status][:8]) + (" ..." if len(problems[status]) > 8 else "")
            report += NL + t(lang, key, n=len(problems[status]), names=names)
    if failed:
        report += NL + NL + t(lang, "announce_fail_note")
    await query.message.edit_text(report, parse_mode="HTML")
    return
    await query.message.edit_text(t(lang, "announce_done", sent=sent, failed=failed))


# Bu handler oxirida turadi: menyu tugmalari e'lon matni bo'lib qolmasligi uchun
@router.message(AnnouncementStates.waiting_text, F.text)
async def handle_announcement_text(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not is_admin_check(current_user):
        await state.clear()
        return

    lang = lang_of(current_user)
    text = (message.text or "").strip()
    target = (await state.get_data()).get("announcement_target", "all")
    recipients = await _announcement_recipients(session, target)
    await state.update_data(announcement_text=text)
    await message.answer(
        t(lang, "announce_preview", text=esc(text), count=len(recipients)) + NL + NL + await _audience_label(session, target, lang),
        parse_mode="HTML",
        reply_markup=announcement_confirm_keyboard(lang),
    )


# --- Bloklash ---
def _protected(user: User) -> bool:
    """Adminlarni bloklab bo'lmaydi"""
    return user.role == UserRole.ADMIN or user.telegram_id in settings.admin_id_list


def _who(user: User) -> str:
    return f"@{esc(user.username)}" if user.username else esc(user.first_name or str(user.telegram_id))


@router.message(Command("block"))
async def handle_block_command(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        return
    query = (message.text or "").partition(" ")[2].strip()
    target = await UserService.find_user(session, query) if query else None
    if not target:
        await message.answer(t(lang, "block_usage"), parse_mode="HTML")
        return
    if _protected(target):
        await message.answer(t(lang, "block_admin_refused"))
        return
    await UserService.set_blocked(session, target, True)
    await message.answer(t(lang, "block_done", who=_who(target)), parse_mode="HTML")


@router.message(Command("unblock"))
async def handle_unblock_command(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        return
    query = (message.text or "").partition(" ")[2].strip()
    target = await UserService.find_user(session, query) if query else None
    if not target:
        await message.answer(t(lang, "block_usage"), parse_mode="HTML")
        return
    await UserService.set_blocked(session, target, False)
    await message.answer(t(lang, "unblock_done", who=_who(target)), parse_mode="HTML")


@router.callback_query(F.data.startswith("blk_"))
async def handle_block_button(query: CallbackQuery, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if not is_admin_check(current_user):
        await query.answer(t(lang, "no_permission"), show_alert=True)
        return
    target = await session.get(User, int(query.data.split("_", 1)[1]))
    if not target:
        await query.answer()
        return
    if _protected(target):
        await query.answer(t(lang, "block_admin_refused"), show_alert=True)
        return
    await UserService.set_blocked(session, target, True)
    await query.answer()
    try:
        await query.message.edit_text(
            f"{query.message.html_text}{NL}{NL}<b>{t(lang, 'block_done', who=_who(target))}</b>",
            parse_mode="HTML", disable_web_page_preview=True,
        )
    except Exception:
        pass
