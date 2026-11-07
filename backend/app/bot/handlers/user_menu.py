from datetime import datetime
import json
import pytz
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.states import ReminderStates
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, SubmissionStatus, UserRole
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.task import PersonalTask
from app.models.user import User
from app.schemas.schedule import ReminderSettingUpdate, ScheduleSubmissionCreate, ScheduleSubmissionReview
from app.services.ai_service import AIService
from app.services.schedule_service import ScheduleService

router = Router(name="user_menu")

DAY_LABELS_UZ = {
    DayOfWeek.MONDAY: "Dushanba",
    DayOfWeek.TUESDAY: "Seshanba",
    DayOfWeek.WEDNESDAY: "Chorshanba",
    DayOfWeek.THURSDAY: "Payshanba",
    DayOfWeek.FRIDAY: "Juma",
    DayOfWeek.SATURDAY: "Shanba",
    DayOfWeek.SUNDAY: "Yakshanba",
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
        await start_registration(message, state)
        return

    today_enum, _ = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id, day_of_week=today_enum)

    if not schedules:
        await message.answer(
            f"📅 <b>Bugun ({DAY_LABELS_UZ[today_enum]}) darslar mavjud emas yoki dam olish kuni!</b>",
            parse_mode="HTML",
        )
        return

    lines = [f"📅 <b>Bugungi darslar ({DAY_LABELS_UZ[today_enum]}):</b>\n"]
    for s in schedules:
        subj = s.subject.name if s.subject else "Fan"
        teacher = f" | {s.teacher.full_name}" if s.teacher else ""
        room = f" | {s.room.number}-xona" if s.room else ""
        lines.append(f"⏰ <b>{s.start_time} - {s.end_time}</b>\n📚 {subj}{room}{teacher}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📆 Ertangi darslar")
async def handle_tomorrow_lessons(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state)
        return

    _, tomorrow_enum = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id, day_of_week=tomorrow_enum)

    if not schedules:
        await message.answer(
            f"📆 <b>Ertaga ({DAY_LABELS_UZ[tomorrow_enum]}) darslar mavjud emas.</b>",
            parse_mode="HTML",
        )
        return

    lines = [f"📆 <b>Ertangi darslar ({DAY_LABELS_UZ[tomorrow_enum]}):</b>\n"]
    for s in schedules:
        subj = s.subject.name if s.subject else "Fan"
        room = f" | {s.room.number}-xona" if s.room else ""
        lines.append(f"⏰ <b>{s.start_time} - {s.end_time}</b>: {subj}{room}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "🗓 Umumiy jadval")
async def handle_full_schedule(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state)
        return

    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
    if not schedules:
        await message.answer(
            "🗓 <b>Guruhingiz uchun hali dars jadvali kiritilmagan.</b>\n\n"
            "Jadval screenshotini <b>📤 Jadval yuborish</b> bo'limi orqali yuboring.",
            parse_mode="HTML",
        )
        return

    by_day: dict[DayOfWeek, list[Schedule]] = {}
    for s in schedules:
        by_day.setdefault(s.day_of_week, []).append(s)

    lines = ["🗓 <b>Haftalik umumiy dars jadvali:</b>\n"]
    for day in DayOfWeek:
        day_schedules = by_day.get(day)
        if not day_schedules:
            continue
        day_schedules.sort(key=lambda s: s.start_time)
        lines.append(f"\n📌 <b>{DAY_LABELS_UZ[day]}</b>")
        for s in day_schedules:
            subj = s.subject.name if s.subject else "Fan"
            teacher = f" | {s.teacher.full_name}" if s.teacher else ""
            room = f" | {s.room.number}-xona" if s.room else ""
            lines.append(f"  ⏰ {s.start_time}-{s.end_time}: {subj}{room}{teacher}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📤 Jadval yuborish")
async def handle_send_schedule_prompt(message: Message, current_user: User, state: FSMContext):
    if not current_user.group_id:
        await start_registration(message, state)
        return

    await message.answer(
        "📸 <b>Dars jadvali screenshotini yuborish:</b>\n\n"
        "Jadval rasmini to'g'ridan-to'g'ri botga <b>rasm (photo)</b> holatida yuboring.\n"
        "AI uni avtomatik tahlil qiladi va darslaringizni darhol jadvalga qo'shib, "
        "eslatmalarni yoqib qo'yadi.",
        parse_mode="HTML",
    )


# --- Dars jadvali screenshotini qabul qilish (Photo Handler) ---
@router.message(F.photo)
async def handle_schedule_photo_upload(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    # Universitet va guruh biriktirilganligini tekshirish - bo'lmasa, avval ro'yxatdan o'tkazamiz
    if not current_user.university_id or not current_user.group_id:
        await start_registration(message, state)
        return

    photo = message.photo[-1]  # eng yuqori sifatlisi
    file_id = photo.file_id

    payload = ScheduleSubmissionCreate(
        university_id=current_user.university_id,
        faculty_id=current_user.faculty_id,
        group_id=current_user.group_id,
        image_file_id=file_id,
        image_url=f"tg://file/{file_id}",
    )
    submission = await ScheduleService.create_submission(session, current_user.id, payload)

    loading_msg = await message.answer(
        "⏳ <b>Screenshot qabul qilindi!</b>\n"
        "Sun'iy intellekt (AI) jadvalni tahlil qilmoqda, iltimos kuting...",
        parse_mode="HTML",
    )

    try:
        processed = await AIService.process_schedule_submission(
            session=session,
            submission_id=submission.id,
            image_bytes=b"tg_image_bytes",
            filename=f"tg_{file_id}.jpg",
        )

        lessons_count = 0
        if processed.ai_extracted_json:
            try:
                lessons_count = len(json.loads(processed.ai_extracted_json))
            except Exception:
                pass

        # Avtomatik tasdiqlash FAQAT shu guruh uchun hali birorta ham dars kiritilmagan bo'lsa
        # (ya'ni guruhni birinchi bo'lib shu talaba "ochyapti") - aks holda, guruh jadvali
        # allaqachon mavjud bo'lsa, uni istalgan a'zo screenshot yuborib osongina buzib
        # qo'ymasligi uchun admin tasdiqlashini kutadi.
        existing_schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id)
        is_admin = current_user.role == UserRole.ADMIN
        can_auto_approve = is_admin or not existing_schedules

        if can_auto_approve:
            review = ScheduleSubmissionReview(
                status=SubmissionStatus.APPROVED,
                admin_notes="Avtomatik tasdiqlandi (guruh uchun birinchi jadval / admin)",
            )
            approved = await ScheduleService.review_submission(session, submission.id, current_user.id, review)

            warning_note = ""
            if approved and approved.admin_notes and "⚠️" in approved.admin_notes:
                warning_note = f"\n\n{approved.admin_notes.strip()}"

            await loading_msg.edit_text(
                f"✅ <b>Jadval muvaffaqiyatli tahlil qilindi va faollashtirildi!</b>\n"
                f"🔍 <b>AI aniqlagan darslar soni:</b> {lessons_count} ta\n\n"
                f"Endi <b>📖 Bugungi darslar</b> va <b>📆 Ertangi darslar</b> bo'limlaridan "
                f"ko'rishingiz, shuningdek darsdan oldin avtomatik eslatma olishingiz mumkin."
                f"{warning_note}",
                parse_mode="HTML",
            )
        else:
            await loading_msg.edit_text(
                f"✅ <b>Jadval tahlil qilindi!</b> ({lessons_count} ta dars aniqlandi)\n\n"
                f"⏳ Sizning guruhingiz uchun jadval allaqachon mavjud, shuning uchun bu "
                f"o'zgartirish xavfsizlik uchun <b>administrator tasdig'ini</b> kutadi - "
                f"tasdiqlangach, barcha guruhdoshlaringizga ko'rinadi.",
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error(f"Error processing bot photo submission: {e}")
        await loading_msg.edit_text(
            f"⚠️ <b>Jadval qabul qilindi (ID #{submission.id}), ammo AI tahlilida xatolik yuz berdi.</b>\n"
            f"Birozdan so'ng qayta urinib ko'ring.",
            parse_mode="HTML",
        )


@router.message(F.text == "📊 Jadval holati")
async def handle_schedule_status(message: Message, current_user: User, session: AsyncSession):
    stmt = select(ScheduleSubmission).where(ScheduleSubmission.user_id == current_user.id).order_by(ScheduleSubmission.id.desc()).limit(3)
    res = await session.execute(stmt)
    subs = res.scalars().all()

    if not subs:
        await message.answer(
            "📊 <b>Siz hali jadval screenshotini yubormagansiz.</b>\n"
            "Yangi jadval yuborish uchun <b>📤 Jadval yuborish</b> bo'limidan foydalaning.",
            parse_mode="HTML",
        )
        return

    lines = ["📊 <b>Sizning oxirgi yuborgan jadvallaringiz:</b>\n"]
    for s in subs:
        st_icon = "⏳" if s.status == SubmissionStatus.PENDING else "🔍" if s.status == SubmissionStatus.ADMIN_REVIEW else "✅" if s.status == SubmissionStatus.APPROVED else "❌"
        lines.append(f"{st_icon} <b>ID:</b> #{s.id} | <b>Holat:</b> {s.status.value}\n📅 Sana: {s.created_at.strftime('%Y-%m-%d %H:%M')}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "⏰ Eslatma sozlamalari")
async def handle_reminder_settings_prompt(message: Message, current_user: User, session: AsyncSession, state: FSMContext):
    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)
    await state.set_state(ReminderStates.waiting_minutes)
    await message.answer(
        f"⏰ <b>Dars eslatmasi sozlamalari</b>\n\n"
        f"Hozirgi sozlama: har bir darsdan <b>{setting.minutes_before} daqiqa</b> oldin eslatma yuboriladi.\n\n"
        f"Yangi qiymatni kiriting (1 dan 180 gacha, daqiqalarda), yoki hech narsa o'zgartirmaslik uchun "
        f"shunchaki <b>0</b> deb yuboring:",
        parse_mode="HTML",
    )


@router.message(ReminderStates.waiting_minutes, F.text)
async def handle_reminder_minutes_input(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer("❗ Iltimos, faqat son kiriting (masalan: 15).")
        return

    value = int(text)
    await state.clear()

    if value == 0:
        await message.answer("ℹ️ Sozlama o'zgartirilmadi.")
        return

    if not (1 <= value <= 180):
        await message.answer("❗ 1 dan 180 gacha bo'lgan qiymat kiriting. Qaytadan <b>⏰ Eslatma sozlamalari</b>ni bosing.", parse_mode="HTML")
        return

    await ScheduleService.update_reminder_setting(
        session, current_user.id, ReminderSettingUpdate(is_enabled=True, minutes_before=value)
    )
    await message.answer(f"✅ Endi darslardan <b>{value} daqiqa</b> oldin eslatma yuboriladi.", parse_mode="HTML")


@router.message(F.text == "👤 Profilim")
async def handle_profile(message: Message, current_user: User, session: AsyncSession):
    role_title = "Administrator" if current_user.role.value == "ADMIN" else "Talaba"

    group_info = "— biriktirilmagan —"
    if current_user.group_id:
        from app.services.university_service import UniversityService

        group = await UniversityService.get_group_by_id(session, current_user.group_id)
        if group:
            group_info = f"{group.name} ({group.university.name if group.university else ''})"

    setting = await ScheduleService.get_or_create_reminder_setting(session, current_user.id)

    info_text = (
        f"👤 <b>Profilingiz:</b>\n\n"
        f"🏷 <b>Ism:</b> {current_user.first_name}\n"
        f"🔰 <b>Rol:</b> {role_title}\n"
        f"👥 <b>Guruh:</b> {group_info}\n"
        f"⏰ <b>Eslatma:</b> darsdan {setting.minutes_before} daqiqa oldin\n\n"
        f"Universitet/fakultet/guruhni qayta kiritish kerak bo'lsa, <b>/register</b> buyrug'ini yuboring."
    )
    await message.answer(info_text, parse_mode="HTML")


@router.message(Command("register"))
async def handle_register_command(message: Message, state: FSMContext):
    await start_registration(message, state)
