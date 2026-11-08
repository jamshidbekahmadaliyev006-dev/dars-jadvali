from typing import Optional
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.i18n import labels, lang_of, t
from app.bot.keyboards.inline import language_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.i18n import format_minutes
from app.bot.keyboards.inline import week_days_keyboard
from app.bot.text_utils import esc, format_weekly_schedule
from app.models.enums import UserRole
from app.models.university import Faculty
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.services.university_service import GENERAL_FACULTY_NAME, UniversityService

router = Router(name="start")


async def _show_welcome(message: Message, state: FSMContext, user: User, session: Optional[AsyncSession]) -> None:
    """Guruhi yo'q foydalanuvchini ro'yxatdan o'tkazadi, aks holda menyuni ochadi"""
    lang = lang_of(user)
    name = esc(user.first_name) or "—"
    is_admin = user.role == UserRole.ADMIN
    welcome_text = t(lang, "welcome_admin" if is_admin else "welcome_student", name=name)

    if not user.group_id:
        await message.answer(welcome_text, parse_mode="HTML")
        await start_registration(message, state, session, lang)
        return

    kb = get_admin_main_keyboard(lang) if is_admin else get_user_main_keyboard(lang)
    if session is None:
        await message.answer(welcome_text, parse_mode="HTML", reply_markup=kb)
        return

    # Ro'yxatdan o'tgan foydalanuvchi: universitet, fakultet, guruh, eslatma va jadval darhol chiqadi
    univ = await UniversityService.get_university_by_id(session, user.university_id) if user.university_id else None
    faculty = await session.get(Faculty, user.faculty_id) if user.faculty_id else None
    group = await UniversityService.get_group_by_id(session, user.group_id)
    setting = await ScheduleService.get_or_create_reminder_setting(session, user.id)

    lines = [welcome_text, "", t(lang, "start_your_data")]
    if univ:
        lines.append(t(lang, "profile_university", name=esc(univ.name)))
    if faculty and faculty.name != GENERAL_FACULTY_NAME:
        lines.append(t(lang, "profile_faculty", name=esc(faculty.name)))
    if group:
        lines.append(t(lang, "profile_group", group=esc(group.name)))
    lines.append(t(lang, "profile_reminder", time=format_minutes(setting.minutes_before, lang)))
    await message.answer("\n".join(lines), parse_mode="HTML", reply_markup=kb)

    schedules = await ScheduleService.get_schedules(session, group_id=user.group_id)
    if schedules:
        await message.answer(
            format_weekly_schedule(schedules, lang), parse_mode="HTML", reply_markup=week_days_keyboard(lang)
        )
    else:
        await message.answer(t(lang, "send_photo_now"), parse_mode="HTML")


@router.message(CommandStart())
async def handle_start(
    message: Message,
    state: FSMContext,
    current_user: User,
    session: Optional[AsyncSession] = None,
    is_new_user: bool = False,
):
    """Kirishda avval til so'raladi, keyin ro'yxatdan o'tish yoki menyu ochiladi"""
    await state.clear()
    if not current_user.language_chosen:
        await message.answer(t(lang_of(current_user), "choose_language"), reply_markup=language_keyboard())
        return

    await _show_welcome(message, state, current_user, session)


@router.message(Command("language"))
@router.message(F.text.in_(labels("btn_language")))
async def handle_language_prompt(message: Message, state: FSMContext, current_user: User):
    await state.clear()
    await message.answer(t(lang_of(current_user), "choose_language"), reply_markup=language_keyboard())


@router.callback_query(F.data.in_({"lang_uz", "lang_ru"}))
async def handle_language_choice(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    lang = query.data.split("_")[-1]
    current_user.language_code = lang
    current_user.language_chosen = True
    await session.commit()

    await query.message.edit_text(t(lang, "language_saved"))
    await query.answer()
    await _show_welcome(query.message, state, current_user, session)
