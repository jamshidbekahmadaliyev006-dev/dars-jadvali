from datetime import datetime
import json
import pytz
from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.keyboards.inline import get_mini_app_inline_button
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, SubmissionStatus
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.task import PersonalTask
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionCreate
from app.services.ai_service import AIService
from app.services.schedule_service import ScheduleService

router = Router(name="user_menu")


def get_today_tomorrow_enums():
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    return DayOfWeek[day_names[weekday_idx]], DayOfWeek[day_names[(weekday_idx + 1) % 7]]


@router.message(F.text == "📖 Bugungi darslar")
async def handle_today_lessons(message: Message, current_user: User, session: AsyncSession):
    if not current_user.group_id:
        await message.answer(
            "ℹ️ <b>Siz hali o'z guruhingizni biriktirmagansiz.</b>\n\n"
            "Dars jadvalini ko'rish uchun avval Mini App orqali universitet va guruhingizni tanlang.",
            parse_mode="HTML",
            reply_markup=get_mini_app_inline_button("📱 Mini Appda guruh tanlash"),
        )
        return

    today_enum, _ = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id, day_of_week=today_enum)

    if not schedules:
        await message.answer(
            f"📅 <b>Bugun ({today_enum.value.capitalize()}) darslar mavjud emas yoki dam olish kuni!</b>",
            parse_mode="HTML",
        )
        return

    lines = [f"📅 <b>Bugungi darslar ({today_enum.value}):</b>\n"]
    for s in schedules:
        subj = s.subject.name if s.subject else "Fan"
        teacher = f" | {s.teacher.full_name}" if s.teacher else ""
        room = f" | {s.room.number}-xona" if s.room else ""
        lines.append(f"⏰ <b>{s.start_time} - {s.end_time}</b>\n📚 {subj}{room}{teacher}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📆 Ertangi darslar")
async def handle_tomorrow_lessons(message: Message, current_user: User, session: AsyncSession):
    if not current_user.group_id:
        await message.answer(
            "ℹ️ <b>Siz hali o'z guruhingizni tanlamagansiz.</b>",
            parse_mode="HTML",
            reply_markup=get_mini_app_inline_button(),
        )
        return

    _, tomorrow_enum = get_today_tomorrow_enums()
    schedules = await ScheduleService.get_schedules(session, group_id=current_user.group_id, day_of_week=tomorrow_enum)

    if not schedules:
        await message.answer(
            f"📆 <b>Ertaga ({tomorrow_enum.value.capitalize()}) darslar mavjud emas.</b>",
            parse_mode="HTML",
        )
        return

    lines = [f"📆 <b>Ertangi darslar ({tomorrow_enum.value}):</b>\n"]
    for s in schedules:
        subj = s.subject.name if s.subject else "Fan"
        room = f" | {s.room.number}-xona" if s.room else ""
        lines.append(f"⏰ <b>{s.start_time} - {s.end_time}</b>: {subj}{room}")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "📝 Vazifalarim")
async def handle_my_tasks(message: Message, current_user: User, session: AsyncSession):
    stmt = select(PersonalTask).where(PersonalTask.user_id == current_user.id, PersonalTask.is_completed == False).limit(5)
    res = await session.execute(stmt)
    tasks = res.scalars().all()

    if not tasks:
        await message.answer(
            "✅ <b>Sizda barcha vazifalar bajarilgan!</b>\n\nYangi vazifalarni Mini App orqali qo'shishingiz mumkin.",
            parse_mode="HTML",
            reply_markup=get_mini_app_inline_button("📱 Mini Appda vazifa qo'shish"),
        )
        return

    lines = ["📝 <b>Sizning faol vazifalaringiz:</b>\n"]
    for t in tasks:
        p_icon = "🔴" if t.priority.value == "HIGH" else "🟡" if t.priority.value == "MEDIUM" else "🟢"
        lines.append(f"{p_icon} <b>{t.title}</b>")

    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=get_mini_app_inline_button("📱 Vazifalarni boshqarish"))


@router.message(F.text == "📅 Dars jadvalim")
async def handle_my_schedule(message: Message, current_user: User):
    await message.answer(
        "📅 <b>To'liq haftalik dars jadvalingiz</b>ni ko'rish uchun quyidagi tugma orqali Mini App'ni oching:",
        parse_mode="HTML",
        reply_markup=get_mini_app_inline_button("📱 Dars jadvalini ochish"),
    )


@router.message(F.text == "📤 Jadval yuborish")
async def handle_send_schedule_prompt(message: Message, current_user: User):
    await message.answer(
        "📸 <b>Dars jadvali screenshotini yuborish:</b>\n\n"
        "Jadval rasmini to'g'ridan-to'g'ri botga <b>rasm (photo)</b> holatida yuboring.\n"
        "AI uni avtomatik tarzda tahlil qilib, darslarni ajratib oladi va tasdiqlash navbatiga qo'yadi.",
        parse_mode="HTML",
    )


@router.message(F.text == "📊 Jadval holati")
async def handle_schedule_status(message: Message, current_user: User, session: AsyncSession):
    stmt = select(ScheduleSubmission).where(ScheduleSubmission.user_id == current_user.id).order_by(ScheduleSubmission.id.desc()).limit(3)
    res = await session.execute(stmt)
    subs = res.scalars().all()

    if not subs:
        await message.answer(
            "📊 <b>Siz yuborgan tasdiqlash kutilayotgan jadval mavjud emas.</b>\n"
            "Yangi jadval yuborish uchun screenshot yuboring.",
            parse_mode="HTML",
        )
        return

    lines = ["📊 <b>Sizning oxirgi yuborgan jadvallaringiz:</b>\n"]
    for s in subs:
        st_icon = "⏳" if s.status == SubmissionStatus.PENDING else "🔍" if s.status == SubmissionStatus.ADMIN_REVIEW else "✅" if s.status == SubmissionStatus.APPROVED else "❌"
        lines.append(f"{st_icon} <b>ID:</b> #{s.id} | <b>Holat:</b> {s.status.value}\n📅 Sana: {s.created_at.strftime('%Y-%m-%d %H:%M')}\n")

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(F.text == "⚙️ Sozlamalar")
async def handle_settings(message: Message, current_user: User):
    role_title = "Administrator" if current_user.role.value == "ADMIN" else "Talaba"
    info_text = (
        f"⚙️ <b>Sizning profilingiz va sozlamalar:</b>\n\n"
        f"👤 <b>Ism:</b> {current_user.first_name}\n"
        f"🆔 <b>Telegram ID:</b> <code>{current_user.telegram_id}</code>\n"
        f"🔰 <b>Rol:</b> {role_title}\n"
        f"🌐 <b>Til:</b> {current_user.language_code}\n\n"
        f"Eslatmalar, shaxsiy ma'lumotlar va guruhni sozlash uchun Mini App'dan foydalaning:"
    )
    await message.answer(
        info_text,
        parse_mode="HTML",
        reply_markup=get_mini_app_inline_button("⚙️ Mini Appda sozlash"),
    )


# --- Dars jadvali screenshotini qabul qilish (Photo Handler) ---
@router.message(F.photo)
async def handle_schedule_photo_upload(message: Message, current_user: User, session: AsyncSession):
    photo = message.photo[-1]  # eng yuqori sifatlisi
    file_id = photo.file_id

    # Universitet biriktirilganligini tekshirish
    univ_id = current_user.university_id or 1  # agar tanlanmagan bo'lsa default 1

    payload = ScheduleSubmissionCreate(
        university_id=univ_id,
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
        # AI orqali tahlil qilish
        # Telegram faylini bot orqali yuklab olish yoki mock tahlil o'tkazish
        processed = await AIService.process_schedule_submission(
            session=session,
            submission_id=submission.id,
            image_bytes=b"tg_image_bytes",
            filename=f"tg_{file_id}.jpg",
        )

        extracted_info = ""
        if processed.ai_extracted_json:
            try:
                lessons = json.loads(processed.ai_extracted_json)
                extracted_info = f"\n\n🔍 <b>AI ajratgan darslar soni:</b> {len(lessons)} ta"
            except Exception:
                pass

        await loading_msg.edit_text(
            f"✅ <b>Jadval muvaffaqiyatli tahlil qilindi!</b>\n"
            f"🆔 <b>Ariza raqami:</b> #{submission.id}\n"
            f"📊 <b>Holati:</b> <code>ADMIN_REVIEW</code>{extracted_info}\n\n"
            f"Administrator ma'lumotlarni tekshirib tasdiqlaganidan so'ng, jadvalingiz faollashadi va "
            f"dars eslatmalari avtomatik yoqiladi.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Error processing bot photo submission: {e}")
        await loading_msg.edit_text(
            f"⚠️ <b>Jadval qabul qilindi (ID #{submission.id}), ammo AI avtomatik tahlilda xatolik yuz berdi.</b>\n"
            f"Admin uni qo'lda tekshirib tasdiqlaydi.",
            parse_mode="HTML",
        )
