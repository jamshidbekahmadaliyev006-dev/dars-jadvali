from datetime import datetime, timedelta
import json
import re
import time
from typing import List, Optional
import pytz
from aiogram import F, Router

from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.album import collect_album, pack_file_ids, send_submission_files, too_small_for_lessons
from app.bot.i18n import NL, format_lesson_count, DAY_LABELS, STATUS_LABELS, format_counts, format_minutes, labels, lang_of, t
from app.bot.keyboards.inline import (
    admin_review_keyboard,
    language_keyboard,
    profile_keyboard,
    reminder_minutes_keyboard,
    week_days_keyboard,
)
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import RegistrationStates, ReminderStates
from app.bot.text_utils import (
    schedule_issues,
    show_typing,
    esc,
    format_date,
    is_full_week,
    week_coverage,
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
    SCHEDULE_VIEW_CACHE,
    SCHEDULE_VIEW_TTL_SECONDS,
    ScheduleService,
    current_local_date,
    canonical_subject_names,
    normalize_subject_name,
    week_parity_for,
)
from app.services.university_service import GENERAL_FACULTY_NAME, UniversityService
from app.services.user_service import UserService

router = Router(name="user_menu")


def _is_change_request(data) -> bool:
    """'Jadval o'zgardi' tugmasidan kelinganmi (state ma'lumotida belgi)"""
    return isinstance(data, dict) and data.get("change_request") is True


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
    title = t(lang, "today_title", day=format_date(current_local_date(), lang))
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
    title = t(lang, "tomorrow_title", day=format_date(current_local_date() + timedelta(days=1), lang))
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

    await show_typing(message)
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

    # Avval javob beramiz - Telegram tugmadagi "yuklanmoqda" belgisini darhol olib tashlaydi
    await query.answer()

    # Hozir ochiq turgan kun yana bosilsa - hech narsa qilmaymiz (keraksiz so'rov yo'q)
    markup = query.message.reply_markup
    if markup and any(
        b.callback_data == query.data and b.text.startswith("•") for row in markup.inline_keyboard for b in row
    ):
        return

    choice = query.data.split("_", 1)[1]
    active = -1 if choice == "all" else int(choice)
    parity = None
    target = None
    if active >= 0:
        today = current_local_date()
        target = today + timedelta(days=active - today.weekday())
        parity = week_parity_for(target)

    cache_key = (current_user.group_id, lang, active, target)
    cached = SCHEDULE_VIEW_CACHE.get(cache_key)
    if cached and time.monotonic() - cached[0] < SCHEDULE_VIEW_TTL_SECONDS:
        text = cached[1]
    else:
        if active == -1:
            schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
            text = format_weekly_schedule(schedules, lang) if schedules else t(lang, "no_schedule")
        else:
            day_enum = list(DayOfWeek)[active]
            schedules = await ScheduleService.get_schedules(
                session, group_id=current_user.group_id, day_of_week=day_enum, week_parity=parity,
            )
            text = format_day_schedule("📅", format_date(target, lang), schedules, lang)
        SCHEDULE_VIEW_CACHE[cache_key] = (time.monotonic(), text)

    try:
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=week_days_keyboard(lang, active))
    except TelegramBadRequest:
        pass  # matn o'zgarmagan


@router.callback_query(F.data == "sched_change")
async def handle_schedule_change(query: CallbackQuery, state: FSMContext, current_user: User):
    """Jadval o'zgardi: yangi rasm yoki matn kutiladi, admin tasdiqlagach guruh jadvali almashadi"""
    await query.answer()
    await state.set_state(RegistrationStates.waiting_schedule)
    await state.update_data(change_request=True)  # o'zgarish faqat admin tasdiqlagach kuchga kiradi
    await query.message.answer(t(lang_of(current_user), "schedule_change_prompt"), parse_mode="HTML")


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
    file_ids: Optional[List[str]] = None,
    is_document: bool = False,
) -> None:
    """Talaba yuborgan BARCHA rasmlarni natijasi bilan adminlarga, har biriga o'z tilida yuboradi"""
    file_ids = file_ids or ([file_id] if file_id and file_id != "text" else [])
    username = f" (@{esc(student.username)})" if student.username else ""

    for admin_id in settings.admin_id_list:
        if admin_id == student.telegram_id and not needs_review:
            continue
        admin_lang = lang_of(await UserService.get_by_telegram_id(session, admin_id))
        lines = [t(admin_lang, "new_schedule", id=submission_id), "", f"👤 {esc(student.first_name)}{username}"]
        if result_key:
            lines.append(t(admin_lang, result_key))
        if lesson_count:
            lines.append(f"📚 {format_counts(subject_count, lesson_count, admin_lang)}")
        markup = admin_review_keyboard(submission_id, admin_lang) if needs_review else None
        try:
            if len(file_ids) > 1:
                await send_submission_files(message.bot, admin_id, file_ids, NL.join(lines), is_document or bool(message.document))
                if markup:  # albom ostiga tugma qo'yib bo'lmaydi - alohida xabar
                    await message.bot.send_message(
                        admin_id, t(admin_lang, "review_buttons", id=submission_id, n=len(file_ids)),
                        parse_mode="HTML", reply_markup=markup,
                    )
            elif file_id and file_id != "text" and message.document:
                await message.bot.send_document(
                    chat_id=admin_id, document=file_id, caption="\n".join(lines), parse_mode="HTML", reply_markup=markup,
                )
            elif file_id and file_id != "text":
                await message.bot.send_photo(
                    chat_id=admin_id, photo=file_id, caption="\n".join(lines), parse_mode="HTML", reply_markup=markup,
                )
            else:
                # Jadval matn ko'rinishida yozilgan - rasm o'rniga matnning o'zi
                lines += ["", f"<pre>{esc((message.text or '')[:3000])}</pre>"]
                await message.bot.send_message(admin_id, "\n".join(lines), parse_mode="HTML", reply_markup=markup)
        except Exception as e:
            logger.error(f"Failed to forward schedule photo to admin {admin_id}: {e}")


# --- Dars jadvali rasmini qabul qilish ---
@router.message(F.photo)
async def handle_schedule_photo_upload(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.university_id or not current_user.group_id:
        await start_registration(message, state, session, lang)
        return

    file_ids = await collect_album(message, message.photo[-1].file_id)
    if file_ids is None:
        return  # albomning keyingi rasmi - birinchisi bilan birga o'qiladi
    change_request = _is_change_request(await state.get_data())
    await state.clear()
    await process_schedule_input(
        message, current_user, session, file_ids=file_ids, change_request=change_request
    )


# Rasm fayl qilib yuborilsa Telegram uni siqmaydi - mayda yozuvlar (bino, xona) aniqroq o'qiladi
@router.message(F.document.mime_type.startswith("image/"))
async def handle_schedule_document_upload(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.university_id or not current_user.group_id:
        await start_registration(message, state, session, lang)
        return
    if (message.document.file_size or 0) > 15 * 1024 * 1024:
        await message.answer(t(lang, "file_too_big"))
        return

    file_ids = await collect_album(message, message.document.file_id)
    if file_ids is None:
        return
    change_request = _is_change_request(await state.get_data())
    await state.clear()
    await process_schedule_input(
        message, current_user, session, file_ids=file_ids, is_document=True, change_request=change_request,
    )


async def _group_mismatch(session: AsyncSession, user: User, lessons: List[dict]) -> Optional[str]:
    """Darslarda ko'rsatilgan guruhlar bor-u, talabaning guruhi ular orasida yo'q bo'lsa - o'sha nom"""
    from app.services.university_service import UniversityService, group_key

    seen = {str(item.get("group")).strip() for item in lessons if item.get("group")}
    if not seen or not user.group_id:
        return None
    group = await UniversityService.get_group_by_id(session, user.group_id)
    if not group:
        return None
    own = group_key(group.name)
    for value in seen:
        # "712-24, 732-24" kabi birgalikdagi yozuvlar
        if own in {group_key(part) for part in re.split(r"[,;]+", value) if part.strip()}:
            return None
    return ", ".join(sorted(seen))[:60]


async def _lookalike_group(session: AsyncSession, user: User, lessons: List[dict]) -> Optional[str]:
    """
    Yangi jadval BOSHQA guruhning mavjud jadvaliga deyarli aynan o'xshasa (90%+), o'sha guruh nomi.
    Odatda bu talaba adashib do'stining/boshqa guruhning rasmini yuborganini bildiradi.
    """
    from app.models.schedule import Schedule
    from app.models.university import Group
    from app.services.schedule_service import normalize_subject_name, resolve_day_of_week
    from sqlalchemy import select as sa_select

    def signature(rows):
        sig = set()
        for item in rows:
            day = resolve_day_of_week(item.get("day"))
            subject = normalize_subject_name(item.get("subject") or "")[0].lower()
            if day and subject and item.get("start_time"):
                sig.add((day.value, item["start_time"], subject))
        return sig

    new_sig = signature(lessons)
    if len(new_sig) < 3:
        return None
    others = (await session.execute(
        sa_select(Schedule).options(selectinload(Schedule.subject))
        .where(Schedule.is_active == True, Schedule.group_id != user.group_id)
    )).scalars().all()
    by_group: dict = {}
    for row in others:
        if row.subject:
            by_group.setdefault(row.group_id, set()).add((row.day_of_week.value, row.start_time, row.subject.name.lower()))
    for group_id, sig in by_group.items():
        union = new_sig | sig
        if union and len(new_sig & sig) / len(union) >= 0.9:
            group = await session.get(Group, group_id)
            return group.name if group else "?"
    return None


async def process_schedule_input(
    message: Message,
    current_user: User,
    session: AsyncSession,
    file_id: Optional[str] = None,
    schedule_text: Optional[str] = None,
    is_document: bool = False,
    change_request: bool = False,
    file_ids: Optional[List[str]] = None,
) -> None:
    """Jadval rasmlari (bir yoki bir nechta) yoki qo'lda yozilgan jadval matnini AI orqali o'qib saqlaydi"""
    lang = lang_of(current_user)
    file_ids = file_ids or ([file_id] if file_id else [])
    file_id = file_ids[0] if file_ids else None
    payload = ScheduleSubmissionCreate(
        university_id=current_user.university_id,
        faculty_id=current_user.faculty_id,
        group_id=current_user.group_id,
        image_file_id=file_id or "text",
        image_url=pack_file_ids(file_ids) if file_ids else f"text:{(schedule_text or '')[:480]}",
    )
    submission = await ScheduleService.create_submission(session, current_user.id, payload)

    loading_msg = await message.answer(t(lang, "reading"))
    await show_typing(message)

    try:
        images: List[bytes] = []
        for fid in file_ids:
            file_info = await message.bot.get_file(fid)
            images.append((await message.bot.download_file(file_info.file_path)).read())
        image_bytes = images[0] if images else b""

        processed = await AIService.process_schedule_submission(
            session=session,
            submission_id=submission.id,
            image_bytes=image_bytes,
            filename=f"tg_{file_id}.jpg",
            text=schedule_text,
            images=images,
        )

        lessons: List[dict] = []
        if processed.ai_extracted_json:
            try:
                lessons = json.loads(processed.ai_extracted_json)
            except Exception:
                pass

        if processed.status != SubmissionStatus.ADMIN_REVIEW or not lessons:
            await loading_msg.edit_text(t(lang, "read_failed"), parse_mode="HTML")
            await _notify_admins(
                message, session, current_user, submission.id, file_id, "admin_read_failed",
                file_ids=file_ids, is_document=is_document,
            )
            return

        # Rasm juda mayda: bir kunga juda kam piksel to'g'ri keladi (matn 9-10 px) - xona va vaqt ishonchsiz
        # o'qiladi. Bunday jadval saqlanmaydi, tiniq rasm so'raladi (Telegram rasmni siqadi: fayl qilib yuborish yordam beradi).
        if file_id and len(images) == 1 and too_small_for_lessons(images[0], lessons):
            processed.status = SubmissionStatus.NEEDS_CORRECTION
            processed.image_file_id = "-"
            processed.image_url = None
            await session.commit()
            await loading_msg.edit_text(t(lang, "schedule_unclear"), parse_mode="HTML")
            return

        # Faqat bitta kun yoki bir-ikki dars (kesilgan rasm) butun guruh jadvali deb SAQLANMAYDI
        if not is_full_week(lessons):
            days, count = week_coverage(lessons)
            processed.status = SubmissionStatus.NEEDS_CORRECTION
            processed.image_file_id = "-"
            processed.image_url = None
            await session.commit()
            await loading_msg.edit_text(
                t(lang, "schedule_partial",
                  days=", ".join(DAY_LABELS[lang][d] for d in days) or "—", lessons=format_lesson_count(count, lang)),
                parse_mode="HTML",
            )
            return

        canonical = canonical_subject_names(lessons)
        subject_count = len({
            code or name.lower()
            for name, code in (normalize_subject_name(item.get("subject") or "") for item in lessons)
        })

        # Talabaga faqat BITTA xabar ("Jadval saqlandi"). Qo'shimcha xabar faqat haqiqiy muammo bo'lsa:
        #  - ba'zi darslar o'qilmadi (kun yoki vaqt aniqlanmadi) yoki
        #  - natija juda yomon (darslarning yarmidan ko'pida xona yo'q) - tiniqroq rasm so'raladi
        from app.services.schedule_service import resolve_day_of_week

        dropped = sum(
            1 for item in lessons
            if not resolve_day_of_week(item.get("day")) or not item.get("start_time") or not item.get("end_time")
        )
        no_room = sum(1 for item in lessons if not item.get("room"))
        poor = bool(file_id) and len(lessons) >= 4 and no_room * 2 >= len(lessons)
        if poor:
            await message.answer(t(lang, "schedule_blurry"), parse_mode="HTML")
        elif dropped:
            await message.answer(t(lang, "lessons_skipped", n=dropped), parse_mode="HTML")

        # Avtomatik tasdiqlash faqat guruhning birinchi jadvali yoki admin uchun: aks holda
        # istalgan a'zo rasm yuborib, butun guruh jadvalini tekshiruvsiz almashtirib qo'yardi.
        existing_schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        is_admin = current_user.role == UserRole.ADMIN
        # Namuna (mock) provayder natijasi hech qachon haqiqiy jadvalga yozilmaydi
        is_real_ai = not isinstance(get_ai_provider(), MockAIProvider)
        # "Jadval o'zgardi" orqali kelgan jadval hech qachon o'zi saqlanmaydi - faqat admin tasdiqlaydi
        # Rasmda boshqa guruh nomi yozilgan bo'lsa (masalan talaba do'stining jadvalini yuborsa) -
        # jadval o'zi saqlanmaydi, admin ko'rib chiqadi
        group_mismatch = await _group_mismatch(session, current_user, lessons)
        if group_mismatch:
            await message.answer(t(lang, "group_mismatch", seen=esc(group_mismatch)), parse_mode="HTML")
        lookalike = None if group_mismatch else await _lookalike_group(session, current_user, lessons)
        if lookalike:
            await message.answer(t(lang, "schedule_lookalike", group=esc(lookalike)), parse_mode="HTML")
        can_auto_approve = (
            is_real_ai and not change_request and not group_mismatch and not lookalike
            and (is_admin or not existing_schedules)
        )

        if not can_auto_approve:
            summary = format_counts(subject_count, len(lessons), lang)
            await loading_msg.edit_text(t(lang, "sent_to_review", summary=summary), parse_mode="HTML")
            await _notify_admins(
                message, session, current_user, submission.id, file_id,
                subject_count=subject_count, lesson_count=len(lessons), needs_review=True,
                file_ids=file_ids, is_document=is_document,
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
            file_ids=file_ids, is_document=is_document,
        )
    except Exception as e:
        logger.error(f"Error processing schedule submission: {e}")
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
        _reminder_prompt_text(lang, setting),
        parse_mode="HTML",
        reply_markup=reminder_minutes_keyboard(lang, setting.is_enabled),
    )


def _reminder_prompt_text(lang: str, setting) -> str:
    if not setting.is_enabled:
        return t(lang, "reminder_prompt_off")
    return t(lang, "reminder_prompt", time=format_minutes(setting.minutes_before, lang))


@router.callback_query(F.data.in_({"remind_off", "remind_on"}))
async def handle_reminder_toggle(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    """Eslatmani o'chirish / qayta yoqish: vaqt sozlamasi saqlanib qoladi"""
    lang = lang_of(current_user)
    enable = query.data == "remind_on"
    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    await ScheduleService.update_reminder_setting(
        session, current_user.id, ReminderSettingUpdate(is_enabled=enable, minutes_before=setting.minutes_before)
    )
    await state.clear()
    text = (
        t(lang, "reminder_saved", time=format_minutes(setting.minutes_before, lang)) if enable
        else t(lang, "reminder_turned_off")
    )
    await query.message.edit_text(text, parse_mode="HTML")
    await query.answer()


@router.callback_query(F.data.regexp(r"^remind_\d+$"))
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
    await show_typing(message)
    lines = [f"👤 <b>{esc(current_user.first_name)}</b>\n"]

    if current_user.group_id:
        group = await UniversityService.get_group_by_id(session, current_user.group_id)
        university = await UniversityService.get_university_by_id(session, current_user.university_id)
        faculty = await session.get(Faculty, current_user.faculty_id) if current_user.faculty_id else None
        if university:
            lines.append(t(lang, "profile_university", name=esc(university.name)))
        if faculty and faculty.name != GENERAL_FACULTY_NAME:
            lines.append(t(lang, "profile_faculty", name=esc(faculty.name)))
        if group:
            lines.append(t(lang, "profile_group", group=esc(group.name)))
        schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        lines.append(f"📚 {schedule_summary(schedules, lang)}" if schedules else t(lang, "profile_no_schedule"))
    else:
        lines.append(t(lang, "profile_no_group"))

    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    lines.append(
        t(lang, "profile_reminder", time=format_minutes(setting.minutes_before, lang)) if setting.is_enabled
        else t(lang, "profile_reminder_off")
    )
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


# --- Hech bir bo'lim tushunmagan xabar: javobsiz qoldirmaymiz ---
@router.message()
async def handle_unknown_message(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    lang = lang_of(current_user)
    if not current_user.group_id:
        from app.services.teacher_service import TeacherService
        if not await TeacherService.get_profile(session, current_user.id):
            from app.bot.handlers.teacher import role_keyboard
            await message.answer(t(lang, "choose_role"), parse_mode="HTML", reply_markup=role_keyboard(lang))
            return
    kb = get_admin_main_keyboard(lang) if current_user.role == UserRole.ADMIN else get_user_main_keyboard(lang)
    await message.answer(t(lang, "fallback_hint"), reply_markup=kb)
