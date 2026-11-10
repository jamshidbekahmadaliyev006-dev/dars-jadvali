"""
O'qituvchilar uchun bot qismi:
- /start da rol tanlash (talaba / o'qituvchi)
- o'qituvchi ro'yxatdan o'tishi -> admin tasdiqlashi
- o'z dars jadvalini rasm/fayl/matn bilan yuborish (AI o'qiydi)
- Dars jadvali / Bugun / Ertaga / Profil o'qituvchining o'z darslari bo'yicha
Talabalar qismiga tegmaydi: barcha handlerlar faqat o'qituvchiga ishlaydi (filtrlar orqali).
"""
import time
from datetime import timedelta
from typing import Any, Dict, List, Optional, Union
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Filter, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.album import collect_album
from app.bot.i18n import DAY_LABELS, NL, TEXTS, format_lesson_count, format_minutes, labels, lang_of, t
from app.bot.keyboards.inline import week_days_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import TeacherStates
from app.bot.text_utils import (
    esc,
    format_date,
    format_teacher_day,
    format_teacher_week,
    looks_like_full_schedule,
    schedule_issues,
    show_typing,
)
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, TeacherStatus, UserRole
from app.models.teacher import TeacherProfile
from app.models.university import University
from app.models.user import User
from app.services.ai_provider import get_ai_provider
from app.services.schedule_service import ScheduleService, current_local_date, week_parity_for
from app.services.name_validation import check_faculty_name, check_university_name, has_bad_word
from app.services.teacher_service import TeacherService
from app.services.user_service import UserService

router = Router(name="teacher")


def _menu_labels() -> set:
    result = set()
    for key in TEXTS:
        if key.startswith("btn_"):
            result |= labels(key)
    return result


class ApprovedTeacher(Filter):
    """Faqat admin tasdiqlagan o'qituvchi; handlerga `teacher` (TeacherProfile) beriladi"""

    async def __call__(self, event: Union[Message, CallbackQuery], current_user: User = None, session: AsyncSession = None) -> Union[bool, Dict[str, Any]]:
        if not current_user or session is None:
            return False
        profile = await TeacherService.get_approved(session, current_user.id)
        return {"teacher": profile} if profile else False


class PendingTeacher(Filter):
    async def __call__(self, event: Message, current_user: User = None, session: AsyncSession = None) -> bool:
        if not current_user or session is None or current_user.group_id:
            return False
        profile = await TeacherService.get_profile(session, current_user.id)
        return bool(profile and profile.status == TeacherStatus.PENDING)


def telegram_account(user: User) -> str:
    """Bosiladigan Telegram nik: @username bo'lsa t.me havolasi, bo'lmasa ismi orqali profilga havola"""
    if user.username:
        return f'<a href="https://t.me/{esc(user.username)}">@{esc(user.username)}</a>'
    full = " ".join(p for p in (user.first_name, user.last_name) if p) or "Telegram"
    return f'<a href="tg://user?id={user.telegram_id}">{esc(full)}</a>'


def role_keyboard(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_role_student"), callback_data="role_student"),
        InlineKeyboardButton(text=t(lang, "btn_role_teacher"), callback_data="role_teacher"),
    ]])


def _teacher_keyboard(user: User, lang: str):
    return get_admin_main_keyboard(lang) if user.role == UserRole.ADMIN else get_user_main_keyboard(lang)


async def show_teacher_home(message: Message, user: User, teacher: TeacherProfile, session: AsyncSession, state: FSMContext) -> None:
    """Tasdiqlangan o'qituvchi /start bosganda: menyu va jadval (yoki jadval so'rash)"""
    lang = lang_of(user)
    lessons = await TeacherService.get_lessons(session, teacher.id)
    await message.answer(
        f"👨‍🏫 <b>{esc(teacher.full_name)}</b>", parse_mode="HTML", reply_markup=_teacher_keyboard(user, lang)
    )
    if lessons:
        await message.answer(format_teacher_week(lessons, lang), parse_mode="HTML", reply_markup=_teacher_week_kb(lang))
    else:
        await state.set_state(TeacherStates.waiting_schedule)
        await message.answer(t(lang, "teacher_send_schedule"), parse_mode="HTML")


def _teacher_week_kb(lang: str, active: int = -1) -> InlineKeyboardMarkup:
    """Talabalarnikidek kun tugmalari, lekin o'qituvchi callback'lari bilan"""
    def remap(data: Optional[str]) -> Optional[str]:
        if data and data.startswith("day_"):
            return "t" + data  # tday_0 ... tday_all
        return "tsched_change" if data == "sched_change" else data

    base = week_days_keyboard(lang, active)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=b.text, callback_data=remap(b.callback_data)) for b in row]
        for row in base.inline_keyboard
    ])


# --- Rol tanlash va ro'yxatdan o'tish ---
@router.callback_query(F.data == "role_student")
async def choose_student(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    await query.answer()
    await query.message.edit_reply_markup(reply_markup=None)
    await start_registration(query.message, state, session, lang_of(current_user))


@router.callback_query(F.data == "role_teacher")
async def choose_teacher(query: CallbackQuery, state: FSMContext, current_user: User):
    await query.answer()
    await query.message.edit_reply_markup(reply_markup=None)
    await state.set_state(TeacherStates.waiting_university)
    await query.message.answer(
        t(lang_of(current_user), "teacher_ask_university"), parse_mode="HTML", reply_markup=ReplyKeyboardRemove()
    )


def _valid(text: str) -> bool:
    return len(text) >= 2 and text[0].isalnum() and text not in _menu_labels()


@router.message(TeacherStates.waiting_university, F.text)
async def teacher_university(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    text = (message.text or "").strip()
    if not _valid(text) or not await check_university_name(session, text):
        await message.answer(t(lang, "bad_university"))
        return
    await state.update_data(t_university=text)
    await state.set_state(TeacherStates.waiting_name)
    await message.answer(t(lang, "teacher_ask_name"))


@router.message(TeacherStates.waiting_name, F.text)
async def teacher_name(message: Message, state: FSMContext, current_user: User):
    lang = lang_of(current_user)
    text = " ".join((message.text or "").split())
    if not _valid(text) or len(text.split()) < 2 or has_bad_word(text) or any(ch.isdigit() for ch in text):
        await message.answer(t(lang, "teacher_bad_name"))
        return
    await state.update_data(t_name=text)
    await state.set_state(TeacherStates.waiting_department)
    await message.answer(t(lang, "teacher_ask_department"))


@router.message(TeacherStates.waiting_department, F.text)
async def teacher_department(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    text = (message.text or "").strip()
    data = await state.get_data()
    if not _valid(text) or not await check_faculty_name(session, text, data.get("t_university")):
        await message.answer(t(lang, "bad_faculty"))
        return
    profile = await TeacherService.submit_profile(
        session, current_user.id, data.get("t_university", ""), data.get("t_name", ""), text
    )
    await state.clear()
    await message.answer(t(lang, "teacher_pending"), parse_mode="HTML")
    await _notify_admins_about_teacher(message, session, current_user, profile)


async def _notify_admins_about_teacher(message: Message, session: AsyncSession, user: User, profile: TeacherProfile) -> None:
    university = await session.get(University, profile.university_id) if profile.university_id else None
    for admin_id in settings.admin_id_list:
        admin_lang = lang_of(await UserService.get_by_telegram_id(session, admin_id))
        kb = _review_kb(admin_lang, profile.id, user.id)
        try:
            await message.bot.send_message(
                admin_id,
                t(
                    admin_lang, "teacher_request_admin",
                    name=esc(profile.full_name),
                    university=esc(university.name if university else "—"),
                    department=esc(profile.department or "—"),
                    who=telegram_account(user),
                ),
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception as e:
            logger.error(f"Failed to send teacher request to admin {admin_id}: {e}")


def _review_kb(lang: str, profile_id: int, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "btn_teacher_ok"), callback_data=f"tch_ok_{profile_id}"),
            InlineKeyboardButton(text=t(lang, "btn_teacher_no"), callback_data=f"tch_no_{profile_id}"),
        ],
        [InlineKeyboardButton(text=t(lang, "btn_block"), callback_data=f"blk_{user_id}")],
    ])


def _block_kb(lang: str, user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_block"), callback_data=f"blk_{user_id}"),
    ]])


async def _teacher_card(session: AsyncSession, profile: TeacherProfile, user: User, lang: str) -> str:
    """Qisqa karta: ism-familiya, fakultet, bosiladigan Telegram nik"""
    icon = {TeacherStatus.APPROVED: "✅", TeacherStatus.PENDING: "⏳"}.get(profile.status, "❌")
    return t(
        lang, "teacher_card",
        icon=icon,
        name=esc(profile.full_name),
        department=esc(profile.department or "—"),
        who=telegram_account(user),
    )


# --- Admin: O'qituvchilar bo'limi ---
def _short_name(full_name: str, limit: int = 22) -> str:
    return full_name if len(full_name) <= limit else full_name[: limit - 1] + "…"


async def _teachers_view(session: AsyncSession, lang: str):
    """O'qituvchilar ro'yxati: (matn, tugmalar). Tugmalar ro'yxat xabarini o'z joyida yangilaydi (tl: prefiksi)."""
    rows = (await session.execute(
        select(TeacherProfile, User).join(User, User.id == TeacherProfile.user_id).order_by(TeacherProfile.full_name)
    )).all()
    counts = {status: sum(1 for p, _ in rows if p.status == status) for status in TeacherStatus}
    lines = [t(lang, "teachers_admin_title", approved=counts[TeacherStatus.APPROVED],
               pending=counts[TeacherStatus.PENDING], rejected=counts[TeacherStatus.REJECTED])]
    keyboard = []

    pending = [(p, u) for p, u in rows if p.status == TeacherStatus.PENDING]
    approved = [(p, u) for p, u in rows if p.status == TeacherStatus.APPROVED]
    if pending:
        lines.append(NL + t(lang, "teachers_pending_title"))
        for n, (p, u) in enumerate(pending, 1):
            lines.append(f"{n}. ⏳ <b>{esc(p.full_name)}</b> — {esc(p.department or '—')} — {telegram_account(u)}")
            keyboard.append([
                InlineKeyboardButton(text=f"✅ {_short_name(p.full_name, 14)}", callback_data=f"tl:ok:{p.id}"),
                InlineKeyboardButton(text="❌", callback_data=f"tl:no:{p.id}"),
                InlineKeyboardButton(text="🚫", callback_data=f"tl:blk:{u.id}"),
            ])
    if approved:
        lines.append(NL + t(lang, "teachers_approved_title"))
        for n, (p, u) in enumerate(approved, 1):
            lines.append(f"{n}. ✅ <b>{esc(p.full_name)}</b> — {esc(p.department or '—')} — {telegram_account(u)}")
            keyboard.append([InlineKeyboardButton(text=f"🚫 {_short_name(p.full_name)}", callback_data=f"tl:blk:{u.id}")])
    return NL.join(lines)[:4000], (InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None)


def _short_name(full_name: str, limit: int = 22) -> str:
    return full_name if len(full_name) <= limit else full_name[: limit - 1] + "…"


@router.message(F.text.in_(labels("btn_teachers")))
async def admin_teachers(message: Message, current_user: User, session: AsyncSession):
    """Hamma o'qituvchilar BITTA xabarda: sanoq, qisqa ro'yxat (ism, fakultet, bosiladigan nik) va tugmalar"""
    lang = lang_of(current_user)
    if current_user.role != UserRole.ADMIN:
        await message.answer(t(lang, "admin_only"))
        return
    text, markup = await _teachers_view(session, lang)
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)


@router.callback_query(F.data.startswith("tl:"))
async def admin_teachers_list_action(query: CallbackQuery, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    if current_user.role != UserRole.ADMIN:
        await query.answer(t(lang, "admin_only"), show_alert=True)
        return
    _, action, raw_id = query.data.split(":")
    target_id = int(raw_id)
    if action == "blk":
        from app.services.user_service import UserService

        target = await session.get(User, target_id)
        if target is None or target.role == UserRole.ADMIN or target.telegram_id in settings.admin_id_list:
            await query.answer(t(lang, "block_admin_refused"), show_alert=True)
            return
        await UserService.set_blocked(session, target, True)
    else:
        await _decide_teacher(query.bot, session, target_id, approve=(action == "ok"))
    await query.answer()
    text, markup = await _teachers_view(session, lang)
    try:
        await query.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=markup)
    except TelegramBadRequest:
        pass


# --- Admin: tasdiqlash / rad etish ---
async def _decide_teacher(bot, session: AsyncSession, profile_id: int, approve: bool):
    """Holatni o'zgartiradi va o'qituvchiga xabar yuboradi"""
    profile = await TeacherService.set_status(
        session, profile_id, TeacherStatus.APPROVED if approve else TeacherStatus.REJECTED
    )
    if not profile:
        return None
    teacher_user = await session.get(User, profile.user_id)
    if not teacher_user:
        return profile
    t_lang = lang_of(teacher_user)
    try:
        if approve:
            await bot.send_message(
                teacher_user.telegram_id, t(t_lang, "teacher_approved"), parse_mode="HTML",
                reply_markup=_teacher_keyboard(teacher_user, t_lang),
            )
            await bot.send_message(teacher_user.telegram_id, t(t_lang, "teacher_send_schedule"), parse_mode="HTML")
        else:
            await bot.send_message(teacher_user.telegram_id, t(t_lang, "teacher_rejected"))
    except Exception as e:
        logger.error(f"Failed to notify teacher {teacher_user.telegram_id}: {e}")
    return profile


@router.callback_query(F.data.startswith("tch_ok_") | F.data.startswith("tch_no_"))
async def admin_review_teacher(query: CallbackQuery, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if current_user.role != UserRole.ADMIN:
        await query.answer(t(lang, "admin_only"), show_alert=True)
        return
    approve = query.data.startswith("tch_ok_")
    profile = await _decide_teacher(query.bot, session, int(query.data.rsplit("_", 1)[1]), approve)
    await query.answer()
    if not profile:
        return
    key = "admin_teacher_approved" if approve else "admin_teacher_rejected"
    try:
        await query.message.edit_text(
            f"{query.message.html_text}\n\n<b>{t(lang, key, name=esc(profile.full_name))}</b>", parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass


# --- Jadval yuklash (rasm / fayl / matn) ---
async def _save_teacher_schedule(
    message: Message, user: User, teacher: TeacherProfile, session: AsyncSession,
    image: Optional[bytes] = None, text: Optional[str] = None, images: Optional[List[bytes]] = None,
) -> None:
    lang = lang_of(user)
    loading = await message.answer(t(lang, "reading"))
    await show_typing(message)
    try:
        provider = get_ai_provider()
        if text:
            result = await provider.extract_schedule_from_text(text)
        elif images and len(images) > 1:
            result = await provider.extract_schedule_from_images(images)
        else:
            result = await provider.extract_schedule_from_image(image or (images[0] if images else b""))
        items = [lesson.model_dump() for lesson in result.lessons]
    except Exception as e:
        logger.error(f"Teacher schedule AI error: {e}")
        await loading.edit_text(t(lang, "read_failed"), parse_mode="HTML")
        return

    from app.bot.album import too_small_for_lessons
    from app.bot.text_utils import MIN_TEACHER_DAYS, MIN_TEACHER_LESSONS, is_full_week, week_coverage

    only_image = (images[0] if images and len(images) == 1 else image) if not text else None
    if only_image and (images is None or len(images) <= 1) and too_small_for_lessons(only_image, items):
        await loading.edit_text(t(lang, "schedule_unclear"), parse_mode="HTML")
        return

    if items and not is_full_week(items, MIN_TEACHER_DAYS, MIN_TEACHER_LESSONS):
        days, count = week_coverage(items)
        await loading.edit_text(
            t(lang, "schedule_partial",
              days=", ".join(DAY_LABELS[lang][d] for d in days) or "—", lessons=format_lesson_count(count, lang)),
            parse_mode="HTML",
        )
        return

    lessons = await TeacherService.replace_lessons(session, teacher.id, items)
    if not lessons:
        await loading.edit_text(t(lang, "read_failed"), parse_mode="HTML")
        return

    _invalidate_teacher_cache(teacher.id)
    setting = await ScheduleService.get_or_create_reminder_setting(session, user.id)
    groups = {l.group_name for l in lessons if l.group_name}
    await loading.edit_text(
        t(lang, "teacher_saved", lessons=format_lesson_count(len(lessons), lang), groups=len(groups),
          time=format_minutes(setting.minutes_before, lang)),
        parse_mode="HTML",
    )

    issues = schedule_issues(items, lang, from_image=image is not None)
    missing_group = [i for i in items if not i.get("group")]
    if missing_group:
        issues.insert(0, f"• {len(missing_group)} — {t(lang, 'issue_group')}")
    if issues:
        await message.answer(
            "\n".join([t(lang, "issues_header"), "", *issues[:10], "", t(lang, "issues_footer")]), parse_mode="HTML"
        )

    all_lessons = await TeacherService.get_lessons(session, teacher.id)
    await message.answer(format_teacher_week(all_lessons, lang), parse_mode="HTML", reply_markup=_teacher_week_kb(lang))


async def _download(message: Message, file_id: str) -> bytes:
    info = await message.bot.get_file(file_id)
    return (await message.bot.download_file(info.file_path)).read()


@router.message(F.photo, ApprovedTeacher())
async def teacher_photo(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    file_ids = await collect_album(message, message.photo[-1].file_id)
    if file_ids is None:
        return
    await state.clear()
    images = [await _download(message, fid) for fid in file_ids]
    await _save_teacher_schedule(message, current_user, teacher, session, image=images[0], images=images)


@router.message(F.document.mime_type.startswith("image/"), ApprovedTeacher())
async def teacher_document(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    if (message.document.file_size or 0) > 15 * 1024 * 1024:
        await message.answer(t(lang_of(current_user), "file_too_big"))
        return
    file_ids = await collect_album(message, message.document.file_id)
    if file_ids is None:
        return
    await state.clear()
    images = [await _download(message, fid) for fid in file_ids]
    await _save_teacher_schedule(message, current_user, teacher, session, image=images[0], images=images)


def _is_schedule_text(message: Message) -> bool:
    text = (message.text or "").strip()
    return bool(text) and not text.startswith("/") and text not in _menu_labels()


@router.message(TeacherStates.waiting_schedule, F.text, _is_schedule_text, ApprovedTeacher())
async def teacher_schedule_text(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    if not looks_like_full_schedule(message.text or ""):
        await message.answer(t(lang_of(current_user), "schedule_text_incomplete"), parse_mode="HTML")
        return
    await state.clear()
    await _save_teacher_schedule(message, current_user, teacher, session, text=message.text.strip())


@router.callback_query(F.data == "tsched_change", ApprovedTeacher())
async def teacher_schedule_change(query: CallbackQuery, state: FSMContext, current_user: User, teacher: TeacherProfile):
    await query.answer()
    await state.set_state(TeacherStates.waiting_schedule)
    await query.message.answer(t(lang_of(current_user), "teacher_send_schedule"), parse_mode="HTML")


# --- Jadvalni ko'rish ---
_TEACHER_CACHE: Dict[tuple, tuple] = {}
_TEACHER_CACHE_TTL = 120


def _invalidate_teacher_cache(teacher_id: int) -> None:
    for key in [k for k in _TEACHER_CACHE if k[0] == teacher_id]:
        _TEACHER_CACHE.pop(key, None)


async def _ask_schedule_if_empty(message: Message, state: FSMContext, lessons: List[Any], lang: str) -> bool:
    if lessons:
        return False
    await state.set_state(TeacherStates.waiting_schedule)
    await message.answer(f"{t(lang, 'teacher_no_schedule')}\n\n{t(lang, 'teacher_send_schedule')}", parse_mode="HTML")
    return True


@router.message(F.text.in_(labels("btn_week")), ApprovedTeacher())
async def teacher_week(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    lang = lang_of(current_user)
    lessons = await TeacherService.get_lessons(session, teacher.id)
    if await _ask_schedule_if_empty(message, state, lessons, lang):
        return
    await show_typing(message)
    await message.answer(format_teacher_week(lessons, lang), parse_mode="HTML", reply_markup=_teacher_week_kb(lang))


@router.message(F.text.in_(labels("btn_today")) | F.text.in_(labels("btn_tomorrow")), ApprovedTeacher())
async def teacher_day(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    lang = lang_of(current_user)
    is_today = message.text in labels("btn_today")
    target = current_local_date() + timedelta(days=0 if is_today else 1)
    lessons = await TeacherService.get_lessons(
        session, teacher.id, list(DayOfWeek)[target.weekday()], week_parity_for(target)
    )
    all_lessons = lessons or await TeacherService.get_lessons(session, teacher.id)
    if await _ask_schedule_if_empty(message, state, all_lessons, lang):
        return
    title = t(lang, "today_title" if is_today else "tomorrow_title", day=format_date(target, lang))
    await message.answer(format_teacher_day("📖" if is_today else "📆", title, lessons, lang), parse_mode="HTML")


@router.callback_query(F.data.startswith("tday_"), ApprovedTeacher())
async def teacher_day_tab(query: CallbackQuery, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    lang = lang_of(current_user)
    await query.answer()
    markup = query.message.reply_markup
    if markup and any(b.callback_data == query.data and b.text.startswith("•") for row in markup.inline_keyboard for b in row):
        return

    choice = query.data.split("_", 1)[1]
    active = -1 if choice == "all" else int(choice)
    target = None
    if active >= 0:
        today = current_local_date()
        target = today + timedelta(days=active - today.weekday())

    key = (teacher.id, lang, active, target)
    cached = _TEACHER_CACHE.get(key)
    if cached and time.monotonic() - cached[0] < _TEACHER_CACHE_TTL:
        text = cached[1]
    else:
        if active == -1:
            lessons = await TeacherService.get_lessons(session, teacher.id)
            text = format_teacher_week(lessons, lang) if lessons else t(lang, "teacher_no_schedule")
        else:
            lessons = await TeacherService.get_lessons(
                session, teacher.id, list(DayOfWeek)[active], week_parity_for(target)
            )
            text = format_teacher_day("📅", format_date(target, lang), lessons, lang)
        _TEACHER_CACHE[key] = (time.monotonic(), text)

    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=_teacher_week_kb(lang, active))
    except TelegramBadRequest:
        pass


@router.message(F.text.in_(labels("btn_profile")), ApprovedTeacher())
async def teacher_profile(message: Message, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    lang = lang_of(current_user)
    university = await session.get(University, teacher.university_id) if teacher.university_id else None
    lessons = await TeacherService.get_lessons(session, teacher.id)
    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    await message.answer(
        t(
            lang, "teacher_profile",
            name=esc(teacher.full_name),
            university=esc(university.name if university else "—"),
            department=esc(teacher.department or "—"),
            lessons=format_lesson_count(len(lessons), lang),
            groups=len({l.group_name for l in lessons if l.group_name}),
            time=format_minutes(setting.minutes_before, lang),
        ),
        parse_mode="HTML",
    )


@router.message(StateFilter(None), F.text, _is_schedule_text, ApprovedTeacher())
async def teacher_free_text(message: Message, state: FSMContext, current_user: User, session: AsyncSession, teacher: TeacherProfile):
    """Tasdiqlangandan keyin jadvali hali yo'q o'qituvchi yozgan matn - bu uning jadvali"""
    if await TeacherService.get_lessons(session, teacher.id):
        return
    if not looks_like_full_schedule(message.text or ""):
        await message.answer(t(lang_of(current_user), "schedule_text_incomplete"), parse_mode="HTML")
        return
    await state.clear()
    await _save_teacher_schedule(message, current_user, teacher, session, text=message.text.strip())


# --- Tasdiq kutayotgan o'qituvchi ---
@router.message(PendingTeacher(), ~F.text.startswith("/"))
async def teacher_waiting(message: Message, current_user: User):
    await message.answer(t(lang_of(current_user), "teacher_still_pending"))
