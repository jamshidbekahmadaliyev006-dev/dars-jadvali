"""
"Mening rejalarim": muhim uchrashuv, kun tartibi, muddat va h.k. Rasm yoki matn yuboriladi, AI voqealarni ajratadi,
foydalanuvchi tasdiqlaydi, bot vaqti kelganda eslatadi. Talaba bo'lmaganlar ("Boshqa") ham shu yerdan foydalanadi.
"""
from typing import List, Optional

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.album import collect_album
from app.bot.handlers.contact import _all_menu_labels
from app.bot.i18n import labels, lang_of, t
from app.bot.keyboards.reply import get_plan_keyboard
from app.bot.states import PlanStates
from app.bot.text_utils import esc
from app.core.logging import logger
from app.models.task import PersonalEvent
from app.models.user import User
from app.services.plan_service import (
    DAILY_AI_LIMIT, MAX_EVENTS_PER_INPUT, ParsedEvent, PlanService, ai_allowed, ai_used, format_when, to_utc_naive,
)

router = Router(name="plans")
MAX_IMAGE_BYTES = 15 * 1024 * 1024


# ---------- ko'rinish ----------
def _line(index: int, when: str, title: str, place: Optional[str]) -> str:
    text = f"{index}. {esc(when)} — <b>{esc(title)}</b>"
    return text + (f"\n    📍 {esc(place)}" if place else "")


def _list_keyboard(lang: str, events: List[PersonalEvent]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=t(lang, "btn_plan_add"), callback_data="plan_add")]]
    dels = [InlineKeyboardButton(text=f"🗑 {i}", callback_data=f"plan_del_{e.id}") for i, e in enumerate(events, 1)]
    for start in range(0, len(dels), 5):
        rows.append(dels[start:start + 5])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_plans(message: Message, user: User, session: AsyncSession, lang: Optional[str] = None) -> None:
    lang = lang or lang_of(user)
    events = await PlanService.upcoming(session, user)
    if not events:
        await message.answer(t(lang, "plans_empty"), parse_mode="HTML", reply_markup=_list_keyboard(lang, []))
        return
    lines = [_line(i, format_when(e.start_time, e.has_time, lang), e.title, e.place) for i, e in enumerate(events, 1)]
    await message.answer(
        t(lang, "plans_header") + "\n\n" + "\n\n".join(lines), parse_mode="HTML", reply_markup=_list_keyboard(lang, events)
    )


@router.message(F.text.in_(labels("btn_plans")))
async def handle_plans_menu(message: Message, state: FSMContext, current_user: User, session: AsyncSession):
    await state.clear()
    await show_plans(message, current_user, session)


@router.callback_query(F.data == "plan_add")
async def handle_plan_add(query: CallbackQuery, state: FSMContext, current_user: User):
    await query.answer()
    await state.set_state(PlanStates.waiting_input)
    await query.message.answer(t(lang_of(current_user), "plans_prompt"), parse_mode="HTML")


# ---------- o'qish ----------
async def _download(message: Message, file_id: str) -> bytes:
    info = await message.bot.get_file(file_id)
    return (await message.bot.download_file(info.file_path)).read()


async def _read_and_preview(message: Message, state: FSMContext, user: User, images: Optional[List[bytes]], text: Optional[str]):
    lang = lang_of(user)
    if not ai_allowed(user.id):
        await message.answer(t(lang, "plans_limit", n=DAILY_AI_LIMIT))
        return
    await message.answer(t(lang, "plans_reading"))
    ai_used(user.id)
    try:
        events = await PlanService.read(images, text)
    except Exception as e:  # noqa: BLE001 - AI band/xato: foydalanuvchiga aytamiz, holat saqlanadi
        logger.error(f"Plans: could not read the input of user {user.id}: {type(e).__name__}: {e}")
        await message.answer(t(lang, "plans_error"))
        return
    if not events:
        await message.answer(t(lang, "plans_none"))
        return

    await state.set_state(None)
    await state.update_data(plan_events=[e.to_dict() for e in events])
    lines = [_line(i, format_when(to_utc_naive(e.day, e.at), e.at is not None, lang), e.title, e.place)
             for i, e in enumerate(events, 1)]
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_plan_save"), callback_data="plan_save"),
        InlineKeyboardButton(text=t(lang, "btn_plan_cancel"), callback_data="plan_cancel"),
    ]])
    await message.answer(t(lang, "plans_found") + "\n\n" + "\n\n".join(lines), parse_mode="HTML", reply_markup=kb)


async def _handle_images(message: Message, state: FSMContext, user: User, file_id: str, is_document: bool):
    lang = lang_of(user)
    if is_document and (message.document.file_size or 0) > MAX_IMAGE_BYTES:
        await message.answer(t(lang, "file_too_big"))
        return
    file_ids = await collect_album(message, file_id)
    if file_ids is None:
        return  # albomning keyingi rasmi - birinchisi bilan birga o'qiladi
    try:
        images = [await _download(message, fid) for fid in file_ids]
    except Exception as e:  # noqa: BLE001
        logger.error(f"Plans: download failed: {e}")
        await message.answer(t(lang, "plans_error"))
        return
    await _read_and_preview(message, state, user, images, (message.caption or "").strip() or None)


async def _handle_text(message: Message, state: FSMContext, user: User):
    text = (message.text or "").strip()
    if text in _all_menu_labels() or text.startswith("/"):
        await state.clear()
        await message.answer(t(lang_of(user), "plans_cancelled"))
        return
    await _read_and_preview(message, state, user, None, text)


@router.message(PlanStates.waiting_input, F.photo)
async def plan_photo(message: Message, state: FSMContext, current_user: User):
    await _handle_images(message, state, current_user, message.photo[-1].file_id, False)


@router.message(PlanStates.waiting_input, F.document.mime_type.startswith("image/"))
async def plan_document(message: Message, state: FSMContext, current_user: User):
    await _handle_images(message, state, current_user, message.document.file_id, True)


@router.message(PlanStates.waiting_input, F.text)
async def plan_text(message: Message, state: FSMContext, current_user: User):
    await _handle_text(message, state, current_user)


# "Boshqa" foydalanuvchi tugma bosmasdan rasm/matn yuborsa: user_menu dagi rasm handlerlari va "tushunarsiz xabar"
# handleri shu yerdagi plan_free_input() ga topshiradi (filterda current_user mavjud emas - middleware undan keyin ishlaydi)
async def plan_free_input(message: Message, state: FSMContext, user: User) -> bool:
    """True - xabar reja sifatida o'qildi (foydalanuvchi "Boshqa" va guruhi yo'q)"""
    if not (user.plan_only and not user.group_id):
        return False
    if message.photo:
        await _handle_images(message, state, user, message.photo[-1].file_id, False)
    elif message.document and (message.document.mime_type or "").startswith("image/"):
        await _handle_images(message, state, user, message.document.file_id, True)
    else:
        text = (message.text or "").strip()
        if not text or text.startswith("/") or text in _all_menu_labels():
            return False
        await _read_and_preview(message, state, user, None, text)
    return True


# ---------- saqlash / bekor / o'chirish ----------
@router.callback_query(F.data == "plan_save")
async def handle_plan_save(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    data = (await state.get_data()).get("plan_events") or []
    await state.clear()
    await query.answer()
    if not data:
        await query.message.edit_text(t(lang, "plans_lost"))
        return
    events = [ParsedEvent.from_dict(d) for d in data][:MAX_EVENTS_PER_INPUT]
    added = await PlanService.add_events(session, current_user, events)
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.answer(t(lang, "plans_saved", n=added), parse_mode="HTML")
    await show_plans(query.message, current_user, session, lang)


@router.callback_query(F.data == "plan_cancel")
async def handle_plan_cancel(query: CallbackQuery, state: FSMContext, current_user: User):
    await state.clear()
    await query.answer()
    await query.message.edit_text(t(lang_of(current_user), "plans_cancelled"))


@router.callback_query(F.data.startswith("plan_del_"))
async def handle_plan_delete(query: CallbackQuery, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    try:
        event_id = int(query.data.rsplit("_", 1)[1])
    except ValueError:
        await query.answer()
        return
    ok = await PlanService.delete(session, current_user, event_id)
    await query.answer(t(lang, "plans_deleted") if ok else t(lang, "plans_lost"))
    if ok:
        try:
            await query.message.delete()
        except Exception:  # noqa: BLE001
            pass
        await show_plans(query.message, current_user, session, lang)


# ---------- "Boshqa" yo'li ----------
@router.callback_query(F.data == "role_other")
async def choose_other(query: CallbackQuery, state: FSMContext, current_user: User, session: AsyncSession):
    lang = lang_of(current_user)
    await query.answer()
    await query.message.edit_reply_markup(reply_markup=None)
    current_user.plan_only = True
    await session.commit()
    await state.clear()
    await query.message.answer(t(lang, "role_other_done"), parse_mode="HTML", reply_markup=get_plan_keyboard(lang))
    await show_plans(query.message, current_user, session, lang)
