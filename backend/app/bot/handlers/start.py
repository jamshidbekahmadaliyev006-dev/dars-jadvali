from typing import Optional
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.handlers.registration import start_registration
from app.bot.i18n import labels, lang_of, t
from app.bot.keyboards.inline import language_keyboard
from app.bot.keyboards.reply import get_admin_main_keyboard, get_plan_keyboard, get_user_main_keyboard
from app.bot.i18n import format_minutes
from app.bot.keyboards.inline import week_days_keyboard
from app.bot.text_utils import esc, format_weekly_schedule
from app.models.enums import UserRole
from app.models.university import Faculty
from app.models.user import User
from app.services.schedule_service import ScheduleService
from app.services.university_service import GENERAL_FACULTY_NAME, UniversityService
from app.services.teacher_service import TeacherService
from app.models.enums import TeacherStatus

router = Router(name="start")


async def _show_welcome(message: Message, state: FSMContext, user: User, session: Optional[AsyncSession]) -> None:
    """Guruhi yo'q foydalanuvchini ro'yxatdan o'tkazadi, aks holda menyuni ochadi"""
    lang = lang_of(user)
    name = esc(user.first_name) or "—"
    is_admin = user.role == UserRole.ADMIN
    welcome_text = t(lang, "welcome_admin" if is_admin else "welcome_student", name=name)

    # O'qituvchi: tasdiqlangan bo'lsa o'z jadvali, kutayotgan bo'lsa holati
    teacher = await TeacherService.get_profile(session, user.id) if session is not None else None
    if teacher and teacher.status == TeacherStatus.APPROVED:
        from app.bot.handlers.teacher import show_teacher_home
        await show_teacher_home(message, user, teacher, session, state)
        return
    if teacher and teacher.status == TeacherStatus.PENDING and not user.group_id:
        await message.answer(t(lang, "teacher_still_pending"))
        return

    if not user.group_id and user.plan_only and session is not None:
        # "Boshqa" foydalanuvchi: talaba emas, faqat rejalar
        from app.bot.handlers.plans import show_plans
        await message.answer(t(lang, "role_other_done"), parse_mode="HTML", reply_markup=get_plan_keyboard(lang))
        await show_plans(message, user, session, lang)
        return

    if not user.group_id:
        # Yangi foydalanuvchi: avval kimligini so'raymiz (talaba, o'qituvchi yoki boshqa)
        from app.bot.handlers.teacher import role_keyboard
        # Faqat qisqa "Tanlang:" va ikkita tugma - ortiqcha matn yo'q
        await message.answer(t(lang, "choose_role"), reply_markup=role_keyboard(lang))
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


@router.callback_query(F.data.in_({"lang_uz", "lang_ru", "lang_en"}))
async def handle_language_choice(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    lang = query.data.split("_")[-1]
    was_chosen = bool(current_user.language_chosen)
    current_user.language_code = lang
    current_user.language_chosen = True
    await session.commit()
    await query.answer()

    # Til keyin almashtirilganda: hech narsa chiqarilmaydi, faqat "qabul qilindi" va menyu yangi tilda
    plan_user = bool(current_user.plan_only and not current_user.group_id)
    if was_chosen and (current_user.group_id or plan_user) or (was_chosen and await TeacherService.get_approved(session, current_user.id)):
        kb = get_admin_main_keyboard(lang) if current_user.role == UserRole.ADMIN else (
            get_plan_keyboard(lang) if plan_user else get_user_main_keyboard(lang))
        try:
            await query.message.delete()
        except Exception:
            pass
        await query.message.answer(t(lang, "language_saved"), reply_markup=kb)
        return

    await query.message.edit_text(t(lang, "language_saved"))
    await _show_welcome(query.message, state, current_user, session)
