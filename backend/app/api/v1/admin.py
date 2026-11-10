"""
Admin sayt API. Har bir so'rov Telegram imzosi (initData) bilan keladi va faqat ADMIN_IDS'dagi
foydalanuvchiga javob beriladi. Boshqa hech kim (shu jumladan oddiy foydalanuvchilar) kira olmaydi.
"""
import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.bot_instance import get_bot
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.core.telegram_auth import TelegramAuthError, verify_init_data
from app.models.enums import SubmissionStatus, UserRole
from app.models.university import Group, University
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionReview
from app.services import admin_service as svc
from app.services.schedule_service import ScheduleService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Admin sayt"])


async def require_admin(
    x_telegram_init_data: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    try:
        tg_user = verify_init_data(x_telegram_init_data or "", settings.BOT_TOKEN)
    except TelegramAuthError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Kirish rad etildi: {e}")
    if not settings.is_admin(tg_user["id"]):
        logger.warning(f"Admin site: non-admin {tg_user.get('id')} tried to open the panel")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu sahifa faqat admin uchun")
    return tg_user


Admin = Depends(require_admin)


async def _uni(session: AsyncSession, uni_id: int) -> University:
    univ = await session.get(University, uni_id)
    if not univ:
        raise HTTPException(status_code=404, detail="Universitet topilmadi")
    return univ


def _bot():
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot ishlamayapti")
    return bot


# ---------------- umumiy ----------------
@router.get("/me")
async def me(admin: Dict[str, Any] = Admin):
    return {"id": admin["id"], "name": " ".join(x for x in (admin.get("first_name"), admin.get("last_name")) if x),
            "username": admin.get("username") or "", "week": svc.current_week()}


@router.get("/universities")
async def universities(admin=Admin, session: AsyncSession = Depends(get_db)):
    return await svc.list_universities(session)


@router.get("/overview")
async def overview(uni: int = Query(...), admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, uni)
    return await svc.overview(session, uni)


# ---------------- foydalanuvchilar ----------------
@router.get("/users")
async def users(
    uni: int = Query(...), q: str = "", stage: str = "", lang: str = "", page: int = 1, size: int = 20,
    admin=Admin, session: AsyncSession = Depends(get_db),
):
    await _uni(session, uni)
    if stage and stage not in svc.STAGES:
        raise HTTPException(status_code=422, detail="Bosqich noto'g'ri")
    return await svc.list_users(session, uni, q=q, stage=stage, lang=lang, page=page, size=size)


@router.get("/users/{user_id}")
async def user_detail(user_id: int, admin=Admin, session: AsyncSession = Depends(get_db)):
    data = await svc.user_detail(session, user_id)
    if not data:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return data


class BlockIn(BaseModel):
    blocked: bool


@router.post("/users/{user_id}/block")
async def block_user(user_id: int, body: BlockIn, admin=Admin, session: AsyncSession = Depends(get_db)):
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if body.blocked and (user.role == UserRole.ADMIN or settings.is_admin(user.telegram_id)):
        raise HTTPException(status_code=400, detail="Adminni bloklab bo'lmaydi")
    await UserService.set_blocked(session, user, body.blocked)
    return {"id": user.id, "active": not body.blocked}


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


@router.post("/users/{user_id}/message")
async def message_user(user_id: int, body: TextIn, admin=Admin, session: AsyncSession = Depends(get_db)):
    from app.bot.sender import OK, safe_send

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    # Admin yozgan matn oddiy matn sifatida ketadi (HTML sifatida o'qilmaydi)
    result, note = await safe_send(_bot(), user.telegram_id, body.text.strip(), parse_mode=None)
    return {"status": result, "note": note}


# ---------------- guruhlar ----------------
@router.get("/groups")
async def groups(uni: int = Query(...), admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, uni)
    return await svc.list_groups(session, uni)


DEFAULT_REMIND = {
    "uz": "📚 Guruhingiz jadvali hali botda yo‘q!\n\nJadval rasmini shu yerga yuboring — har darsdan oldin bot o‘zi eslatadi 👇",
    "ru": "📚 Расписания вашей группы пока нет в боте!\n\nОтправьте фото расписания сюда — бот будет напоминать перед каждой парой 👇",
    "en": "📚 Your group's timetable is not in the bot yet!\n\nSend a photo of the timetable here and the bot will remind you before every class 👇",
}


@router.post("/groups/{group_id}/remind")
async def remind_group(group_id: int, admin=Admin, session: AsyncSession = Depends(get_db)):
    from app.bot.sender import OK, safe_send

    group = await session.get(Group, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Guruh topilmadi")
    bot = _bot()
    members = await svc.group_members(session, group_id)
    sent = 0
    for member in members:
        text = DEFAULT_REMIND.get(member.language_code or "uz", DEFAULT_REMIND["uz"])
        result, _ = await safe_send(bot, member.telegram_id, text, parse_mode=None)
        sent += result == OK
        await asyncio.sleep(0.04)
    return {"total": len(members), "sent": sent}


# ---------------- jadval so'rovlari ----------------
@router.get("/submissions")
async def submissions(uni: int = Query(...), admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, uni)
    return await svc.list_submissions(session, uni)


@router.get("/submissions/{sub_id}")
async def submission(sub_id: int, admin=Admin, session: AsyncSession = Depends(get_db)):
    data = await svc.submission_detail(session, sub_id)
    if not data:
        raise HTTPException(status_code=404, detail="So'rov topilmadi")
    return data


class LessonsIn(BaseModel):
    lessons: List[Dict[str, Any]]


@router.put("/submissions/{sub_id}/lessons")
async def save_lessons(sub_id: int, body: LessonsIn, admin=Admin, session: AsyncSession = Depends(get_db)):
    try:
        result = await svc.save_submission_lessons(session, sub_id, body.lessons)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {**result, "submission": await svc.submission_detail(session, sub_id)}


class ReviewIn(BaseModel):
    action: str  # approve | reject


async def _notify_after_review(sub_id: int, approved: bool, user_id: int, group_id: Optional[int]) -> None:
    """Talabaga natija va (tasdiqlansa) guruhdoshlarga 'jadval yangilandi' xabari - botdagi bilan bir xil"""
    from app.bot.i18n import lang_of, t
    from app.bot.sender import safe_send
    from app.bot.text_utils import esc
    from app.core.database import AsyncSessionLocal

    bot = get_bot()
    if not bot:
        return
    async with AsyncSessionLocal() as session:
        student = await session.get(User, user_id)
        if student:
            await safe_send(bot, student.telegram_id, t(lang_of(student), "student_approved" if approved else "student_rejected"),
                            parse_mode="HTML")
        if approved and group_id:
            group = await session.get(Group, group_id)
            for member in await svc.group_members(session, group_id):
                if member.id == user_id:
                    continue
                await safe_send(bot, member.telegram_id,
                                t(lang_of(member), "group_schedule_updated", group=esc(group.name if group else "")),
                                parse_mode="HTML")
                await asyncio.sleep(0.05)


@router.post("/submissions/{sub_id}/review")
async def review(sub_id: int, body: ReviewIn, admin: Dict[str, Any] = Admin, session: AsyncSession = Depends(get_db)):
    if body.action not in ("approve", "reject"):
        raise HTTPException(status_code=422, detail="Amal noto'g'ri")
    sub = await ScheduleService.get_submission_by_id(session, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="So'rov topilmadi")
    if sub.status not in svc.OPEN_STATUSES:
        raise HTTPException(status_code=409, detail="Bu so'rov allaqachon ko'rib chiqilgan")
    reviewer = await session.scalar(select(User).where(User.telegram_id == admin["id"]))
    approved = body.action == "approve"
    updated = await ScheduleService.review_submission(
        session, sub_id, reviewer.id if reviewer else None,
        ScheduleSubmissionReview(
            status=SubmissionStatus.APPROVED if approved else SubmissionStatus.REJECTED,
            admin_notes="Admin sayt orqali tasdiqlandi" if approved else "Admin sayt orqali rad etildi",
        ),
    )
    warning = updated.admin_notes if updated and updated.admin_notes and "⚠️" in updated.admin_notes else ""
    if not warning:
        asyncio.create_task(_notify_after_review(sub_id, approved, sub.user_id, sub.group_id))
    return {"status": updated.status.value, "warning": warning, "submission": await svc.submission_detail(session, sub_id)}


# ---------------- xabarlar ----------------
@router.get("/broadcast/audiences")
async def audiences(uni: int = Query(...), admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, uni)
    return await svc.audience_counts(session, uni)


@router.get("/broadcast")
async def broadcast_history(uni: int = Query(...), admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, uni)
    return await svc.broadcast_history(session, uni)


class BroadcastIn(BaseModel):
    uni: int
    audience: str
    text: str = Field(min_length=1, max_length=4000)


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, body.uni)
    if body.audience not in svc.AUDIENCES:
        raise HTTPException(status_code=422, detail="Auditoriya noto'g'ri")
    job = await svc.start_broadcast(session, _bot(), body.uni, body.audience, body.text.strip())
    logger.info(f"Admin site broadcast {job['id']} by {admin['id']}: {job['total']} recipients ({body.audience})")
    return job


@router.get("/broadcast/{ann_id}")
async def broadcast_status(ann_id: int, admin=Admin):
    job = svc.BROADCASTS.get(ann_id)
    if not job:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return job
