from typing import List, Optional
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import RegistrationStates
from app.bot.text_utils import esc, format_weekly_schedule
from app.models.enums import UserRole
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.services.university_service import UniversityService

router = Router(name="registration")


def _options_keyboard(names: List[str]):
    """Bazadagi nomlarni tugma qiladi: guruhdoshlar bir xil tanlab, tayyor jadvalga tushadi"""
    if not names:
        return ReplyKeyboardRemove()
    rows = [[KeyboardButton(text=name)] for name in names[:30]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


async def start_registration(message: Message, state: FSMContext, session: Optional[AsyncSession] = None) -> None:
    """Talabani universitet -> fakultet -> guruh bosqichlari orqali ro'yxatdan o'tkazishni boshlaydi"""
    universities = await UniversityService.get_all_universities(session) if session else []
    await state.set_state(RegistrationStates.waiting_university)
    await message.answer(
        "🏛 <b>Qaysi universitetda o'qiysiz?</b>\n\n"
        "Pastdan tanlang yoki nomini to'liq yozing:",
        parse_mode="HTML",
        reply_markup=_options_keyboard([u.name for u in universities]),
    )


@router.message(RegistrationStates.waiting_university, F.text)
async def process_university(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❗ Iltimos, universitet nomini to'liqroq yozing.")
        return

    univ = await UniversityService.find_university_by_name(session, name)
    faculties = await UniversityService.get_faculties_by_university(session, univ.id) if univ else []

    await state.update_data(university_name=name)
    await state.set_state(RegistrationStates.waiting_faculty)
    await message.answer(
        "🏢 <b>Fakultetingizni tanlang yoki nomini yozing</b> (masalan: Dasturiy injiniring):",
        parse_mode="HTML",
        reply_markup=_options_keyboard([f.name for f in faculties]),
    )


@router.message(RegistrationStates.waiting_faculty, F.text)
async def process_faculty(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❗ Iltimos, fakultet nomini to'liqroq yozing.")
        return

    data = await state.get_data()
    univ = await UniversityService.find_university_by_name(session, data.get("university_name", ""))
    faculty = await UniversityService.find_faculty_by_name(session, univ.id, name) if univ else None
    groups = await UniversityService.get_groups(session, univ.id, faculty.id) if faculty else []

    await state.update_data(faculty_name=name)
    await state.set_state(RegistrationStates.waiting_group)
    await message.answer(
        "👥 <b>Guruhingizni tanlang yoki nomini yozing</b> (masalan: 101-21):",
        parse_mode="HTML",
        reply_markup=_options_keyboard([g.name for g in groups]),
    )


@router.message(RegistrationStates.waiting_group, F.text)
async def process_group(
    message: Message,
    state: FSMContext,
    current_user: User,
    session: AsyncSession,
) -> None:
    name = (message.text or "").strip()
    if not name:
        await message.answer("❗ Iltimos, guruh nomini kiriting.")
        return

    data = await state.get_data()
    university_name = data.get("university_name", "")
    faculty_name = data.get("faculty_name", "")

    univ = await UniversityService.get_or_create_university_by_name(session, university_name)
    faculty = await UniversityService.get_or_create_faculty_by_name(session, univ.id, faculty_name)
    group = await UniversityService.get_or_create_group_by_name(session, univ.id, faculty.id, name)

    current_user.university_id = univ.id
    current_user.faculty_id = faculty.id
    current_user.group_id = group.id
    await session.commit()

    await state.clear()

    kb = get_admin_main_keyboard() if current_user.role == UserRole.ADMIN else get_user_main_keyboard()
    profile_text = (
        f"✅ <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"🏛 <b>Universitet:</b> {esc(univ.name)}\n"
        f"🏢 <b>Fakultet:</b> {esc(faculty.name)}\n"
        f"👥 <b>Guruh:</b> {esc(group.name)}\n\n"
    )

    # Guruhdoshi jadvalni allaqachon kiritgan bo'lsa, rasm so'ramasdan darhol ishga tushadi
    schedules = await ScheduleService.get_schedules(session, group_id=group.id)
    if schedules:
        await message.answer(
            f"{profile_text}"
            f"🎉 Guruhingiz jadvali bazada bor, rasm yuborishingiz shart emas. "
            f"Eslatmalar sizga ham yoqildi.",
            parse_mode="HTML",
            reply_markup=kb,
        )
        await message.answer(format_weekly_schedule(schedules), parse_mode="HTML")
        return

    await message.answer(
        f"{profile_text}"
        f"Endi dars jadvali rasmini yuboring. Men uni o'qib, jadvalingizga qo'shaman va "
        f"eslatmalarni yoqaman 📸",
        parse_mode="HTML",
        reply_markup=kb,
    )
