from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.keyboards.reply import get_admin_main_keyboard, get_user_main_keyboard
from app.bot.states import RegistrationStates
from app.bot.text_utils import esc
from app.models.enums import UserRole
from app.models.user import User
from app.services.university_service import UniversityService

router = Router(name="registration")


async def start_registration(message: Message, state: FSMContext) -> None:
    """Talabani universitet -> fakultet -> guruh bosqichlari orqali ro'yxatdan o'tkazishni boshlaydi"""
    await state.set_state(RegistrationStates.waiting_university)
    await message.answer(
        "🏛 <b>Qaysi universitetda o'qiysiz?</b>\n\n"
        "Nomini to'liq yozib yuboring (masalan: <i>Toshkent Axborot Texnologiyalari Universiteti</i>):",
        parse_mode="HTML",
    )


@router.message(RegistrationStates.waiting_university, F.text)
async def process_university(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❗ Iltimos, universitet nomini to'liqroq yozing.")
        return

    await state.update_data(university_name=name)
    await state.set_state(RegistrationStates.waiting_faculty)
    await message.answer(
        "🏢 <b>Endi fakultet nomini yozing</b> (masalan: Dasturiy injiniring):",
        parse_mode="HTML",
    )


@router.message(RegistrationStates.waiting_faculty, F.text)
async def process_faculty(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer("❗ Iltimos, fakultet nomini to'liqroq yozing.")
        return

    await state.update_data(faculty_name=name)
    await state.set_state(RegistrationStates.waiting_group)
    await message.answer(
        "👥 <b>Guruh nomini/raqamini yozing</b> (masalan: 101-21):",
        parse_mode="HTML",
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
    await message.answer(
        f"✅ <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>\n\n"
        f"🏛 <b>Universitet:</b> {esc(univ.name)}\n"
        f"🏢 <b>Fakultet:</b> {esc(faculty.name)}\n"
        f"👥 <b>Guruh:</b> {esc(group.name)}\n\n"
        f"Endi dars jadvali screenshotini yuboring — men uni avtomatik o'qib, "
        f"jadvalingizga qo'shib, eslatmalarni yoqib qo'yaman 📸",
        parse_mode="HTML",
        reply_markup=kb,
    )
