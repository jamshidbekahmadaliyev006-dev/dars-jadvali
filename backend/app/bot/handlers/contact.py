from aiogram import F, Router

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession
from app.bot.i18n import TEXTS, labels, lang_of, t
from app.bot.keyboards.inline import contact_reply_keyboard
from app.bot.states import ContactStates
from app.bot.text_utils import esc, show_typing
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import UserRole
from app.models.user import User
from app.services.user_service import UserService

router = Router(name="contact")

MAX_CONTACT_LENGTH = 3000


def _all_menu_labels() -> set:
    result = set()
    for key in TEXTS:
        if key.startswith("btn_"):
            result |= labels(key)
    return result


@router.message(F.text.in_(labels("btn_contact")))
async def handle_contact_start(message: Message, state: FSMContext, current_user: User):
    """Murojaat: talaba matn yozishni boshlaydi"""
    lang = lang_of(current_user)
    await state.set_state(ContactStates.waiting_message)
    await show_typing(message)
    await message.answer(t(lang, "contact_prompt"), parse_mode="HTML")


@router.message(ContactStates.waiting_message, F.text)
async def handle_contact_message(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    text = (message.text or "").strip()

    # Foydalanuvchi boshqa menyu tugmasini bossa - murojaat bekor qilinadi
    if text in _all_menu_labels() or text.startswith("/"):
        await state.clear()
        await message.answer(t(lang, "contact_cancelled"))
        return

    if not settings.admin_id_list:
        await state.clear()
        await message.answer(t(lang, "contact_no_admin"))
        return

    username = f" (@{esc(current_user.username)})" if current_user.username else ""
    who = f"{esc(current_user.first_name)}{username}"
    delivered = 0
    await show_typing(message)
    for admin_id in settings.admin_id_list:
        admin_lang = lang_of(await UserService.get_by_telegram_id(session, admin_id))
        try:
            await message.bot.send_message(
                admin_id,
                t(admin_lang, "contact_new", who=who, text=esc(text[:MAX_CONTACT_LENGTH])),
                parse_mode="HTML",
                reply_markup=contact_reply_keyboard(current_user.telegram_id, admin_lang),
            )
            delivered += 1
        except Exception as e:
            logger.error(f"Failed to deliver contact message to admin {admin_id}: {e}")

    await state.clear()
    await message.answer(t(lang, "contact_sent") if delivered else t(lang, "contact_no_admin"))


@router.callback_query(F.data.startswith("contact_reply_"))
async def handle_admin_reply_start(query: CallbackQuery, state: FSMContext, current_user: User):
    lang = lang_of(current_user)
    if current_user.role != UserRole.ADMIN:
        await query.answer(t(lang, "admin_only"), show_alert=True)
        return

    target_id = int(query.data.rsplit("_", 1)[1])
    await state.set_state(ContactStates.waiting_admin_reply)
    await state.update_data(reply_to=target_id)
    await query.answer()
    await query.message.answer(t(lang, "contact_reply_prompt", who=f"<code>{target_id}</code>"), parse_mode="HTML")


@router.message(ContactStates.waiting_admin_reply, F.text)
async def handle_admin_reply(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    data = await state.get_data()
    target_id = data.get("reply_to")
    text = (message.text or "").strip()

    if text in _all_menu_labels() or text.startswith("/") or not target_id:
        await state.clear()
        await message.answer(t(lang, "contact_cancelled"))
        return

    student = await UserService.get_by_telegram_id(session, target_id)
    student_lang = lang_of(student)
    try:
        await message.bot.send_message(
            target_id,
            t(student_lang, "contact_from_admin", text=esc(text[:MAX_CONTACT_LENGTH])),
            parse_mode="HTML",
        )
        await message.answer(t(lang, "contact_reply_sent"))
    except Exception as e:
        logger.error(f"Failed to deliver admin reply to {target_id}: {e}")
        await message.answer(t(lang, "contact_reply_failed"))
    await state.clear()
