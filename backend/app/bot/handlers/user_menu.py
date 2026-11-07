from datetime import datetime, timedelta
import json
from typing import List
import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.keyboards.inline import admin_review_keyboard, reminder_minutes_keyboard
from app.bot.states import ReminderStates
from app.bot.text_utils import (
    DAY_LABELS_UZ,
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
from app.models.user import User
from app.schemas.schedule import ReminderSettingUpdate, ScheduleSubmissionCreate, ScheduleSubmissionReview
from app.services.ai_provider import MockAIProvider, get_ai_provider
from app.services.ai_service import AIService
from app.services.schedule_service import (
    ScheduleService,
    current_local_date,
    format_minutes_uz,
    normalize_subject_name,
    week_parity_for,
)
from app.services.university_service import UniversityService

router = Router(name="user_menu")

STATUS_LABELS_UZ = {
    SubmissionStatus.PENDING: "⏳ Qabul qilindi",
    SubmissionStatus.AI_PROCESSING: "⏳ O'qilmoqda",
    SubmissionStatus.AI_COMPLETED: "⏳ O'qildi",
    SubmissionStatus.ADMIN_REVIEW: "🔍 Admin tekshiruvida",
    SubmissionStatus.APPROVED: "✅ Tasdiqlangan",
    SubmissionStatus.REJECTED: "❌ Rad etilgan",
    SubmissionStatus.NEEDS_CORRECTION: "⚠️ O'qib bo'lmadi",
}


def get_today_tomorrow_enums():
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    return DayOfWeek[day_names[weekday_idx]], DayOfWeek[day_names[(weekday_idx + 1) % 7]]


@router.message(F.text == "📖 Bugungi darslar")
async def handle_today_lessons(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state, session)
        return

    today_enum, _ = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(
        session,
        group_id=current_user.group_id,
        day_of_week=today_enum,
        week_parity=week_parity_for(current_local_date()),
    )
    title = f"Bugun, {DAY_LABELS_UZ[today_enum]}"
    await message.answer(format_day_schedule("📖", title, schedules), parse_mode="HTML")


@router.message(F.text == "📆 Ertangi darslar")
async def handle_tomorrow_lessons(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state, session)
        return

    _, tomorrow_enum = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(
        session,
        group_id=current_user.group_id,
        day_of_week=tomorrow_enum,
        week_parity=week_parity_for(current_local_date() + timedelta(days=1)),
    )
    title = f"Ertaga, {DAY_LABELS_UZ[tomorrow_enum]}"
    await message.answer(format_day_schedule("📆", title, schedules), parse_mode="HTML")


@router.message(F.text == "🗓 Umumiy jadval")
async def handle_full_schedule(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state, session)
        return

    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
    if not schedules:
        await message.answer("🗓 Jadvalingiz hali yo'q.\n\nJadval rasmini shu yerga yuboring.")
        return

    await message.answer(format_weekly_schedule(schedules), parse_mode="HTML")


@router.message(F.text == "📤 Jadval yuborish")
async def handle_send_schedule_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state, session)
        return

    await message.answer("📸 Jadval rasmini shu yerga yuboring.")


async def _notify_admins(
    message: Message,
    student: User,
    submission_id: int,
    file_id: str,
    result_line: str,
    needs_review: bool,
) -> None:
    """Talaba yuborgan rasmni natijasi bilan adminlarga yuboradi"""
    username = f" (@{esc(student.username)})" if student.username else ""
    caption = (
        f"📸 <b>Yangi jadval #{submission_id}</b>\n\n"
        f"👤 {esc(student.first_name)}{username}\n"
        f"{result_line}"
    )
    keyboard = admin_review_keyboard(submission_id) if needs_review else None

    for admin_id in settings.admin_id_list:
        if admin_id == student.telegram_id:
            continue
        try:
            await message.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.error(f"Failed to forward schedule photo to admin {admin_id}: {e}")


# --- Dars jadvali rasmini qabul qilish ---
@router.message(F.photo)
async def handle_schedule_photo_upload(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.university_id or not current_user.group_id:
        await start_registration(message, state, session)
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

    loading_msg = await message.answer("⏳ Jadval o'qilmoqda, bir necha soniya kuting...")

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
            await loading_msg.edit_text(
                "⚠️ <b>Jadvalni o'qib bo'lmadi</b>\n\n"
                "Hech narsa saqlanmadi. Aniqroq rasm yuboring yoki birozdan so'ng qayta urinib ko'ring.",
                parse_mode="HTML",
            )
            await _notify_admins(message, current_user, submission.id, file_id, "⚠️ AI o'qiy olmadi", False)
            return

        subject_count = len({normalize_subject_name(item.get("subject") or "")[0].lower() for item in lessons})
        result_line = f"📚 {subject_count} ta fan · {len(lessons)} ta dars"

        # Avtomatik tasdiqlash faqat guruhning birinchi jadvali yoki admin uchun: aks holda
        # istalgan a'zo rasm yuborib, butun guruh jadvalini tekshiruvsiz almashtirib qo'yardi.
        existing_schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        is_admin = current_user.role == UserRole.ADMIN
        # Namuna (mock) provayder natijasi hech qachon haqiqiy jadvalga yozilmaydi
        is_real_ai = not isinstance(get_ai_provider(), MockAIProvider)
        can_auto_approve = is_real_ai and (is_admin or not existing_schedules)

        if not can_auto_approve:
            await loading_msg.edit_text(
                f"🔍 <b>Admin tekshiruviga yuborildi</b>\n\n"
                f"{result_line}\n\n"
                f"Guruhingiz jadvali allaqachon bor. Admin tasdiqlasa, yangisi bilan almashtiriladi.",
                parse_mode="HTML",
            )
            await _notify_admins(message, current_user, submission.id, file_id, result_line, True)
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
            f"✅ <b>Jadval saqlandi</b>\n\n"
            f"{schedule_summary(schedules)}\n\n"
            f"{numbered}\n\n"
            f"⏰ Eslatma har darsdan {format_minutes_uz(setting.minutes_before)} oldin keladi.",
            parse_mode="HTML",
        )
        await _notify_admins(message, current_user, submission.id, file_id, f"✅ Saqlandi\n{result_line}", False)
    except Exception as e:
        logger.error(f"Error processing bot photo submission: {e}")
        await loading_msg.edit_text(
            "⚠️ <b>Xatolik yuz berdi</b>\n\nJadval saqlanmadi. Birozdan so'ng qayta yuboring.",
            parse_mode="HTML",
        )


@router.message(F.text == "📊 Jadval holati")
async def handle_schedule_status(message: Message, current_user: User, session: AsyncSession):
    stmt = (
        select(ScheduleSubmission)
        .where(ScheduleSubmission.user_id == current_user.id)
        .order_by(ScheduleSubmission.id.desc())
        .limit(3)
    )
    subs = (await session.execute(stmt)).scalars().all()

    if not subs:
        await message.answer("📊 Siz hali jadval yubormagansiz.")
        return

    lines = ["📊 <b>Oxirgi yuborgan jadvallaringiz</b>\n"]
    for s in subs:
        label = STATUS_LABELS_UZ.get(s.status, s.status.value)
        lines.append(f"{s.created_at.strftime('%d.%m.%Y')} — {label}")

    await message.answer("\n".join(lines), parse_mode="HTML")


async def _save_reminder_minutes(session: AsyncSession, user: User, minutes: int) -> str:
    await ScheduleService.update_reminder_setting(
        session, user.id, ReminderSettingUpdate(is_enabled=True, minutes_before=minutes)
    )
    return f"✅ Eslatma endi darsdan <b>{format_minutes_uz(minutes)}</b> oldin keladi."


@router.message(F.text == "⏰ Eslatma sozlamalari")
async def handle_reminder_settings_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    await state.set_state(ReminderStates.waiting_minutes)
    await message.answer(
        f"⏰ <b>Eslatma vaqti</b>\n\n"
        f"Hozir: darsdan {format_minutes_uz(setting.minutes_before)} oldin.\n\n"
        f"Yangi vaqtni tanlang yoki daqiqada yozing (1–180):",
        parse_mode="HTML",
        reply_markup=reminder_minutes_keyboard(),
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
        await message.answer("❗ 1 dan 180 gacha son yozing. Masalan: 30")
        return

    await state.clear()
    await message.answer(await _save_reminder_minutes(session, current_user, int(text)), parse_mode="HTML")


@router.message(F.text == "👤 Profilim")
async def handle_profile(message: Message, current_user: User, session: AsyncSession):
    lines = [f"👤 <b>{esc(current_user.first_name)}</b>\n"]

    if current_user.group_id:
        group = await UniversityService.get_group_by_id(session, current_user.group_id)
        university = await UniversityService.get_university_by_id(session, current_user.university_id)
        if university:
            lines.append(f"🏛 {esc(university.name)}")
        if group:
            lines.append(f"👥 Guruh: {esc(group.name)}")
        schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        lines.append(f"📚 {schedule_summary(schedules)}" if schedules else "📚 Jadval hali yo'q")
    else:
        lines.append("👥 Guruh tanlanmagan")

    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    lines.append(f"⏰ Eslatma: darsdan {format_minutes_uz(setting.minutes_before)} oldin")
    lines.append("\nGuruhni o'zgartirish: /register")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("register"))
async def handle_register_command(message: Message, session: AsyncSession, state: FSMContext):
    await start_registration(message, state, session)
