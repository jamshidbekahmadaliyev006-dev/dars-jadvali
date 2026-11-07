from typing import List, Optional
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.i18n import DEFAULT_LANG, lang_of, t
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import RegistrationStates
from app.bot.text_utils import esc, format_weekly_schedule
from app.models.enums import UserRole
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.services.university_service import UniversityService

router = Router(name="registration")


def _is_valid_name(name: str, min_length: int = 2) -> bool:
    # Menyu tugmasi yoki buyruq nom bo'lib saqlanib qolmasin
    return len(name) >= min_length and name[0].isalnum()


def _options_keyboard(names: List[str]):
    """Bazadagi nomlarni tugma qiladi: guruhdoshlar bir xil tanlab, tayyor jadvalga tushadi"""
    if not names:
        return ReplyKeyboardRemove()
    rows = [[KeyboardButton(text=name)] for name in names[:30]]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True, one_time_keyboard=True)


async def start_registration(
    message: Message,
    state: FSMContext,
    session: Optional[AsyncSession] = None,
    lang: str = DEFAULT_LANG,
) -> None:
    """Talabani universitet -> fakultet -> guruh bosqichlari orqali ro'yxatdan o'tkazishni boshlaydi"""
    universities = await UniversityService.get_all_universities(session) if session else []
    await state.set_state(RegistrationStates.waiting_university)
    await message.answer(
        t(lang, "ask_university"),
        parse_mode="HTML",
        reply_markup=_options_keyboard([u.name for u in universities]),
    )


@router.message(RegistrationStates.waiting_university, F.text)
async def process_university(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    if not _is_valid_name(name):
        await message.answer(t(lang, "bad_university"))
        return

    univ = await UniversityService.find_university_by_name(session, name)
    faculties = await UniversityService.get_faculties_by_university(session, univ.id) if univ else []

    await state.update_data(university_name=name)
    await state.set_state(RegistrationStates.waiting_faculty)
    await message.answer(
        t(lang, "ask_faculty"),
        parse_mode="HTML",
        reply_markup=_options_keyboard([f.name for f in faculties]),
    )


@router.message(RegistrationStates.waiting_faculty, F.text)
async def process_faculty(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    if not _is_valid_name(name):
        await message.answer(t(lang, "bad_faculty"))
        return

    data = await state.get_data()
    univ = await UniversityService.find_university_by_name(session, data.get("university_name", ""))
    faculty = await UniversityService.find_faculty_by_name(session, univ.id, name) if univ else None
    groups = await UniversityService.get_groups(session, univ.id, faculty.id) if faculty else []

    await state.update_data(faculty_name=name)
    await state.set_state(RegistrationStates.waiting_group)
    await message.answer(
        t(lang, "ask_group"),
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
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    if not _is_valid_name(name, min_length=1):
        await message.answer(t(lang, "bad_group"))
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

    is_admin = current_user.role == UserRole.ADMIN
    kb = get_admin_main_keyboard(lang) if is_admin else get_user_main_keyboard(lang)
    profile_text = f"{t(lang, 'registered')}\n\n🏛 {esc(univ.name)}\n🏢 {esc(faculty.name)}\n👥 {esc(group.name)}\n\n"

    # Guruhdoshi jadvalni allaqachon kiritgan bo'lsa, rasm so'ramasdan darhol ishga tushadi
    schedules = await ScheduleService.get_schedules(session, group_id=group.id)
    if schedules:
        await message.answer(f"{profile_text}{t(lang, 'group_ready')}", parse_mode="HTML", reply_markup=kb)
        await message.answer(format_weekly_schedule(schedules, lang), parse_mode="HTML")
        return

    await message.answer(f"{profile_text}{t(lang, 'send_photo_now')}", parse_mode="HTML", reply_markup=kb)
