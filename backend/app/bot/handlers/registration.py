from typing import Optional
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.i18n import DEFAULT_LANG, TEXTS, labels, lang_of, t
from app.bot.keyboards.inline import week_days_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import RegistrationStates
from app.bot.text_utils import esc, format_weekly_schedule
from app.models.enums import UserRole
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.models.university import Faculty
from app.services.name_validation import check_faculty_name, check_group_name, check_university_name
from app.services.university_service import GENERAL_FACULTY_NAME, UniversityService

router = Router(name="registration")


def _menu_labels() -> set:
    result = set()
    for key in TEXTS:
        if key.startswith("btn_"):
            result |= labels(key)
    return result


def _is_valid_name(name: str, min_length: int = 2) -> bool:
    # Menyu tugmasi yoki buyruq nom bo'lib saqlanib qolmasin
    return len(name) >= min_length and name[0].isalnum() and name not in _menu_labels()


async def start_registration(
    message: Message,
    state: FSMContext,
    session: Optional[AsyncSession] = None,
    lang: str = DEFAULT_LANG,
) -> None:
    """
    Ro'yxatdan o'tish: faqat universitet va guruh so'raladi, ikkalasi ham qo'lda yoziladi.
    Bazadagi nomlar tugma qilib ko'rsatilmaydi - talabalar adashib boshqa guruhni bosib yubormasin.
    """
    await state.set_state(RegistrationStates.waiting_university)
    await message.answer(t(lang, "ask_university"), parse_mode="HTML", reply_markup=ReplyKeyboardRemove())


@router.message(RegistrationStates.waiting_university, F.text)
async def process_university(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    if not _is_valid_name(name) or not await check_university_name(session, name):
        await message.answer(t(lang, "bad_university"))
        return

    await state.update_data(university_name=name)
    await state.set_state(RegistrationStates.waiting_faculty)
    await message.answer(t(lang, "ask_faculty"), parse_mode="HTML")


@router.message(RegistrationStates.waiting_faculty, F.text)
async def process_faculty(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    university_name = (await state.get_data()).get("university_name")
    if not _is_valid_name(name) or not await check_faculty_name(session, name, university_name):
        await message.answer(t(lang, "bad_faculty"))
        return

    await state.update_data(faculty_name=name)
    await state.set_state(RegistrationStates.waiting_group)
    await message.answer(t(lang, "ask_group"), parse_mode="HTML")


@router.message(RegistrationStates.waiting_group, F.text)
async def process_group(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    lang = lang_of(current_user)
    name = (message.text or "").strip()
    if not _is_valid_name(name, min_length=1) or not check_group_name(name):
        await message.answer(t(lang, "bad_group"))
        return

    data = await state.get_data()
    univ, group = await UniversityService.register_university_and_group(
        session, data.get("university_name", ""), name, faculty_name=data.get("faculty_name")
    )
    faculty = await session.get(Faculty, group.faculty_id)

    current_user.university_id = univ.id
    current_user.faculty_id = group.faculty_id
    current_user.group_id = group.id
    await session.commit()
    await state.clear()

    is_admin = current_user.role == UserRole.ADMIN
    kb = get_admin_main_keyboard(lang) if is_admin else get_user_main_keyboard(lang)
    faculty_line = f"🎓 {esc(faculty.name)}\n" if faculty and faculty.name != GENERAL_FACULTY_NAME else ""
    profile_text = f"{t(lang, 'registered')}\n\n🏛 {esc(univ.name)}\n{faculty_line}👥 {esc(group.name)}\n\n"

    # Guruh jadvali bazada bo'lsa - darhol ko'rsatiladi, rasm so'ralmaydi
    schedules = await ScheduleService.get_schedules(session, group_id=group.id)
    if schedules:
        await message.answer(f"{profile_text}{t(lang, 'group_ready')}", parse_mode="HTML", reply_markup=kb)
        await message.answer(
            format_weekly_schedule(schedules, lang), parse_mode="HTML", reply_markup=week_days_keyboard(lang)
        )
        return

    # Jadval yo'q - rasm yoki matn ko'rinishida so'raladi
    await state.set_state(RegistrationStates.waiting_schedule)
    await message.answer(f"{profile_text}{t(lang, 'send_photo_now')}", parse_mode="HTML", reply_markup=kb)


def _is_schedule_text(message: Message) -> bool:
    # Menyu tugmalari va buyruqlar jadval matni emas - ular o'z handlerlariga o'tadi
    text = (message.text or "").strip()
    return bool(text) and not text.startswith("/") and text not in _menu_labels()


@router.message(RegistrationStates.waiting_schedule, F.text, _is_schedule_text)
async def process_schedule_text(message: Message, state: FSMContext, current_user: User, session: AsyncSession) -> None:
    """Talaba jadvalni yozib yubordi: AI matndan darslarni ajratib oladi"""
    text = (message.text or "").strip()
    await state.clear()
    from app.bot.handlers.user_menu import process_schedule_input
    await process_schedule_input(message, current_user, session, schedule_text=text)
