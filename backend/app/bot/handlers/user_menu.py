from datetime import datetime, timedelta
import json
from typing import List
import pytz
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.i18n import DAY_LABELS, STATUS_LABELS, format_counts, format_minutes, labels, lang_of, t
from app.bot.keyboards.inline import (
    admin_review_keyboard,
    language_keyboard,
    profile_keyboard,
    reminder_minutes_keyboard,
    week_days_keyboard,
)
from app.bot.states import ReminderStates
from app.bot.text_utils import (
    esc,
    format_day_schedule,
    format_weekly_schedule,
    schedule_summary,
    subject_names,
)
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, SubmissionStatus, UserRole
from app.models.schedule import ScheduleSubmission
from app.models.university import Faculty
from app.models.user import User
from app.schemas.schedule import ReminderSettingUpdate, ScheduleSubmissionCreate, ScheduleSubmissionReview
from app.services.ai_provider import MockAIProvider, get_ai_provider
from app.services.ai_service import AIService
from app.services.schedule_service import (
    ScheduleService,
    current_local_date,
    normalize_subject_name,
    week_parity_for,
)
from app.services.university_service import UniversityService
from app.services.user_service import UserService

router = Router(name="user_menu")


def get_today_tomorrow_enums():
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    return DayOfWeek[day_names[weekday_idx]], DayOfWeek[day_names[(weekday_idx + 1) % 7]]


@router.message(F.text.in_(labels("btn_today")))
async def handle_today_lessons(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    today_enum, _ = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(
        session,
        group_id=current_user.group_id,
        day_of_week=today_enum,
        week_parity=week_parity_for(current_local_date()),
    )
    title = t(lang, "today_title", day=DAY_LABELS[lang][today_enum])
    await message.answer(format_day_schedule("📖", title, schedules, lang), parse_mode="HTML")


@router.message(F.text.in_(labels("btn_tomorrow")))
async def handle_tomorrow_lessons(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    _, tomorrow_enum = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(
        session,
        group_id=current_user.group_id,
        day_of_week=tomorrow_enum,
        week_parity=week_parity_for(current_local_date() + timedelta(days=1)),
    )
    title = t(lang, "tomorrow_title", day=DAY_LABELS[lang][tomorrow_enum])
    await message.answer(format_day_schedule("📆", title, schedules, lang), parse_mode="HTML")


@router.message(F.text.in_(labels("btn_week")))
async def handle_full_schedule(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
    if not schedules:
        await message.answer(t(lang, "no_schedule"))
        return

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    await message.answer(
        format_weekly_schedule(schedules, lang),
        parse_mode="HTML",
        reply_markup=week_days_keyboard(lang),
    )


@router.callback_query(F.data.startswith("day_"))
async def handle_day_tab(query: CallbackQuery, current_user: User, session: AsyncSession):
    """Dars jadvali ostidagi kun tugmalari: xabar o'sha joyida almashadi"""
    lang = lang_of(current_user)
    if not current_user.group_id:
        await query.answer(t(lang, "no_schedule"), show_alert=True)
        return

    choice = query.data.split("_", 1)[1]
    if choice == "all":
        active = -1
        schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        text = format_weekly_schedule(schedules, lang) if schedules else t(lang, "no_schedule")
    else:
        active = int(choice)
        day_enum = list(DayOfWeek)[active]
        today = current_local_date()
        target = today + timedelta(days=active - today.weekday())
        schedules = await ScheduleService.get_schedules(
            session,
            group_id=current_user.group_id,
            day_of_week=day_enum,
            week_parity=week_parity_for(target),
        )
        text = format_day_schedule("📅", DAY_LABELS[lang][day_enum], schedules, lang)

    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=week_days_keyboard(lang, active))
    except TelegramBadRequest:
        pass  # xuddi shu kun qayta bosildi - matn o'zgarmagan
    await query.answer()


@router.message(F.text.in_(labels("btn_send")))
async def handle_send_schedule_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    await message.answer(t(lang, "send_prompt"))


async def _notify_admins(
    message: Message,
    session: AsyncSession,
    student: User,
    submission_id: int,
    file_id: str,
    result_key: str = "",
    subject_count: int = 0,
    lesson_count: int = 0,
    needs_review: bool = False,
) -> None:
    """Talaba yuborgan rasmni natijasi bilan adminlarga, har biriga o'z tilida yuboradi"""
    username = f" (@{esc(student.username)})" if student.username else ""

    for admin_id in settings.admin_id_list:
        if admin_id == student.telegram_id:
            continue
        admin_lang = lang_of(await UserService.get_by_telegram_id(session, admin_id))
        lines = [t(admin_lang, "new_schedule", id=submission_id), "", f"👤 {esc(student.first_name)}{username}"]
        if result_key:
            lines.append(t(admin_lang, result_key))
        if lesson_count:
            lines.append(f"📚 {format_counts(subject_count, lesson_count, admin_lang)}")
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption="\n".join(lines),
                parse_mode="HTML",
                reply_markup=admin_review_keyboard(submission_id, admin_lang) if needs_review else None,
            )
        except Exception as e:
            logger.error(f"Failed to forward schedule photo to admin {admin_id}: {e}")


# --- Dars jadvali rasmini qabul qilish ---
@router.message(F.photo)
async def handle_schedule_photo_upload(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.university_id or not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    file_id = message.photo[-1].file_id  # eng yuqori sifatlisi

    payload = ScheduleSubmissionCreate(
        university_id=current_user.university_id,
        faculty_id=current_user.faculty_id,
        group_id=current_user.group_id,
        image_file_id=file_id,
        image_url=f"tg://file/{file_id}",
    )
    submission = await ScheduleService.create_submission(session, current_user.id, payload)

    loading_msg = await message.answer(t(lang, "reading"))

    try:
        file_info = await message.bot.get_file(file_id)
        file_io = await message.bot.download_file(file_info.file_path)

        processed = await AIService.process_schedule_submission(
            session=session,
            submission_id=submission.id,
            image_bytes=file_io.read(),
            filename=f"tg_{file_id}.jpg",
        )

        lessons: List[dict] = []
        if processed.ai_extracted_json:
            try:
                lessons = json.loads(processed.ai_extracted_json)
            except Exception:
                pass

        if processed.status != SubmissionStatus.ADMIN_REVIEW or not lessons:
            await loading_msg.edit_text(t(lang, "read_failed"), parse_mode="HTML")
            await _notify_admins(message, session, current_user, submission.id, file_id, "admin_read_failed")
            return

        subject_count = len({normalize_subject_name(item.get("subject") or "")[0].lower() for item in lessons})

        # Avtomatik tasdiqlash faqat guruhning birinchi jadvali yoki admin uchun: aks holda
        # istalgan a'zo rasm yuborib, butun guruh jadvalini tekshiruvsiz almashtirib qo'yardi.
        existing_schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        is_admin = current_user.role == UserRole.ADMIN
        # Namuna (mock) provayder natijasi hech qachon haqiqiy jadvalga yozilmaydi
        is_real_ai = not isinstance(get_ai_provider(), MockAIProvider)
        can_auto_approve = is_real_ai and (is_admin or not existing_schedules)

        if not can_auto_approve:
            summary = format_counts(subject_count, len(lessons), lang)
            await loading_msg.edit_text(t(lang, "sent_to_review", summary=summary), parse_mode="HTML")
            await _notify_admins(
                message, session, current_user, submission.id, file_id,
                subject_count=subject_count, lesson_count=len(lessons), needs_review=True,
            )
            return

        review = ScheduleSubmissionReview(
            status=SubmissionStatus.APPROVED,
            admin_notes="Avtomatik tasdiqlandi (guruh uchun birinchi jadval / admin)",
        )
        await ScheduleService.review_submission(session, submission.id, current_user.id, review)

        schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
        numbered = "\n".join(f"{i}. {esc(name)}" for i, name in enumerate(subject_names(schedules), start=1))

        await loading_msg.edit_text(
            t(
                lang,
                "saved",
                summary=schedule_summary(schedules, lang),
                subjects=numbered,
                time=format_minutes(setting.minutes_before, lang),
            ),
            parse_mode="HTML",
        )
        await _notify_admins(
            message, session, current_user, submission.id, file_id, "admin_saved",
            subject_count=subject_count, lesson_count=len(lessons),
        )
    except Exception as e:
        logger.error(f"Error processing bot photo submission: {e}")
        await loading_msg.edit_text(t(lang, "upload_error"), parse_mode="HTML")


@router.message(F.text.in_(labels("btn_status")))
async def handle_schedule_status(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    stmt = (
        select(ScheduleSubmission)
        .where(ScheduleSubmission.user_id == current_user.id)
        .order_by(ScheduleSubmission.id.desc())
        .limit(3)
    )
    subs = (await session.execute(stmt)).scalars().all()

    if not subs:
        await message.answer(t(lang, "status_empty"))
        return

    lines = [t(lang, "status_title")]
    for s in subs:
        label = STATUS_LABELS[lang].get(s.status, s.status.value)
        lines.append(f"{s.created_at.strftime('%d.%m.%Y')} — {label}")

    await message.answer("\n".join(lines), parse_mode="HTML")


async def _save_reminder_minutes(session: AsyncSession, user: User, minutes: int) -> str:
    await ScheduleService.update_reminder_setting(
        session, user.id, ReminderSettingUpdate(is_enabled=True, minutes_before=minutes)
    )
    lang = lang_of(user)
    return t(lang, "reminder_saved", time=format_minutes(minutes, lang))


@router.message(F.text.in_(labels("btn_reminder")))
async def handle_reminder_settings_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    await state.set_state(ReminderStates.waiting_minutes)
    await message.answer(
        t(lang, "reminder_prompt", time=format_minutes(setting.minutes_before, lang)),
        parse_mode="HTML",
        reply_markup=reminder_minutes_keyboard(lang),
    )


@router.callback_query(F.data.startswith("remind_"))
async def handle_reminder_minutes_button(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    minutes = int(query.data.split("_")[-1])
    await state.clear()
    text = await _save_reminder_minutes(session, current_user, minutes)
    await query.message.edit_text(text, parse_mode="HTML")
    await query.answer()


@router.message(ReminderStates.waiting_minutes, F.text)
async def handle_reminder_minutes_input(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    text = (message.text or "").strip()
    if not text.isdigit() or not (1 <= int(text) <= 180):
        await message.answer(t(lang_of(current_user), "reminder_bad"))
        return

    await state.clear()
    await message.answer(await _save_reminder_minutes(session, current_user, int(text)), parse_mode="HTML")


@router.message(F.text.in_(labels("btn_profile")))
async def handle_profile(message: Message, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    lines = [f"👤 <b>{esc(current_user.first_name)}</b>\n"]

    if current_user.group_id:
        group = await UniversityService.get_group_by_id(session, current_user.group_id)
        university = await UniversityService.get_university_by_id(session, current_user.university_id)
        faculty = await session.get(Faculty, current_user.faculty_id) if current_user.faculty_id else None
        if university:
            lines.append(t(lang, "profile_university", name=esc(university.name)))
        if faculty:
            lines.append(t(lang, "profile_faculty", name=esc(faculty.name)))
        if group:
            lines.append(t(lang, "profile_group", group=esc(group.name)))
        schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        lines.append(f"📚 {schedule_summary(schedules, lang)}" if schedules else t(lang, "profile_no_schedule"))
    else:
        lines.append(t(lang, "profile_no_group"))

    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    lines.append(t(lang, "profile_reminder", time=format_minutes(setting.minutes_before, lang)))
    lines.append(t(lang, "profile_lang"))

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=profile_keyboard(lang))


@router.callback_query(F.data == "profile_group")
async def handle_profile_change_group(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    await query.answer()
    await start_registration(query.message, state, session, lang_of(current_user))


@router.callback_query(F.data == "profile_lang")
async def handle_profile_change_language(query: CallbackQuery, current_user: User):
    await query.answer()
    await query.message.answer(t(lang_of(current_user), "choose_language"), reply_markup=language_keyboard())


@router.message(Command("register"))
async def handle_register_command(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    await start_registration(message, state, session, lang_of(current_user))
