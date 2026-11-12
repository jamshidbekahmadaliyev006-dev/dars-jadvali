"""
Admin sayt API. Kirish: botdagi "Admin sayt" tugmasi bergan bir martalik havola -> /login -> sessiya tokeni.
Har bir so'rovda sessiya tekshiriladi va admin hali ADMIN_IDS'da ekani qayta tasdiqlanadi.
"""
import asyncio
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.bot_instance import get_bot
from app.core.admin_session import create_session_token, exchange_login_token, verify_session
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import logger
from app.models.enums import SubmissionStatus, UserRole
from app.models.university import Group, University
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionReview
from app.services import admin_service as svc
from app.services.schedule_service import ScheduleService
from app.services.user_service import UserService

router = APIRouter(prefix="/admin", tags=["Admin sayt"])


async def require_admin(authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else ""
    telegram_id = verify_session(token)
    if telegram_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kirish rad etildi: sessiya yo'q yoki tugagan")
    if not settings.is_admin(telegram_id):
        logger.warning(f"Admin site: {telegram_id} is no longer an admin")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu sahifa faqat admin uchun")
    return {"id": telegram_id}


Admin = Depends(require_admin)


async def _uni(session: AsyncSession, uni: int) -> int:
    """uni=0 - barcha universitetlar (botdagi umumiy raqamlar)"""
    if uni and not await session.get(University, uni):
        raise HTTPException(status_code=404, detail="Universitet topilmadi")
    return uni


def _bot():
    bot = get_bot()
    if not bot:
        raise HTTPException(status_code=503, detail="Bot ishlamayapti")
    return bot


# ---------------- kirish ----------------
class LoginIn(BaseModel):
    token: str = Field(min_length=1, max_length=2000)


@router.post("/login")
async def login(body: LoginIn):
    """Botdagi tugma bergan bir martalik havolani sessiyaga almashtiradi"""
    telegram_id = exchange_login_token(body.token)
    if telegram_id is None:
        raise HTTPException(status_code=401, detail="Havola eskirgan yoki oldin ishlatilgan")
    if not settings.is_admin(telegram_id):
        raise HTTPException(status_code=403, detail="Bu sahifa faqat admin uchun")
    return {"session": create_session_token(telegram_id)}


@router.get("/me")
async def me(admin: Dict[str, Any] = Admin, session: AsyncSession = Depends(get_db)):
    user = await session.scalar(select(User).where(User.telegram_id == admin["id"]))
    name = " ".join(x for x in (user.first_name, user.last_name) if x) if user else ""
    return {"id": admin["id"], "name": name or "Admin", "username": (user.username if user else "") or "", "week": svc.current_week()}


@router.get("/universities")
async def universities(admin=Admin, session: AsyncSession = Depends(get_db)):
    return await svc.list_universities(session)


@router.get("/overview")
async def overview(uni: int = Query(0), day: str = "", admin=Admin, session: AsyncSession = Depends(get_db)):
    return await svc.overview(session, await _uni(session, uni), svc.day_end_utc(day))


@router.get("/activity")
async def activity(
    uni: int = Query(0), period: str = Query("day", pattern="^(day|week|month)$"), day: str = "",
    admin=Admin, session: AsyncSession = Depends(get_db),
):
    return await svc.activity(session, await _uni(session, uni), period, day)


# ---------------- foydalanuvchilar ----------------
@router.get("/users")
async def users(
    uni: int = Query(0), q: str = "", stage: str = "", lang: str = "", page: int = 1, size: int = 20,
    admin=Admin, session: AsyncSession = Depends(get_db),
):
    if stage and stage not in svc.STAGES:
        raise HTTPException(status_code=422, detail="Bosqich noto'g'ri")
    return await svc.list_users(session, await _uni(session, uni), q=q, stage=stage, lang=lang, page=page, size=size)


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
    from app.bot.sender import safe_send

    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    # Admin yozgan matn oddiy matn sifatida ketadi (HTML sifatida o'qilmaydi)
    result, note = await safe_send(_bot(), user.telegram_id, body.text.strip(), parse_mode=None)
    return {"status": result, "note": note}


# ---------------- guruhlar ----------------
@router.get("/groups")
async def groups(uni: int = Query(0), admin=Admin, session: AsyncSession = Depends(get_db)):
    return await svc.list_groups(session, await _uni(session, uni))


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
async def submissions(
    uni: int = Query(0), status: str = "", limit: int = 50, offset: int = 0, admin=Admin, session: AsyncSession = Depends(get_db),
):
    """status: bitta yoki vergul bilan bir nechta holat (masalan ADMIN_REVIEW yoki PENDING,AI_PROCESSING)"""
    wanted: List[SubmissionStatus] = []
    for name in [s.strip() for s in status.split(",") if s.strip()]:
        if name not in SubmissionStatus.__members__:
            raise HTTPException(status_code=422, detail="Holat noto'g'ri")
        wanted.append(SubmissionStatus[name])
    return await svc.list_submissions(session, await _uni(session, uni), wanted or None, limit, offset)


@router.get("/notifications")
async def notifications(since: int = Query(0), admin=Admin, session: AsyncSession = Depends(get_db)):
    """Qo'ng'iroqcha: oxirgi qo'shilgan foydalanuvchilar va ko'rib chiqilishi kerak so'rovlar soni (hamma universitetlar)"""
    return await svc.notifications(session, since)


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
    reason: Optional[str] = Field(default=None, max_length=500)  # rad etishda: talabaga nima xato ekani


async def _review_messages(session: AsyncSession, sub, approved: bool, reason: str) -> List[Tuple[int, str]]:
    """Qaror haqida xabarlar: talabaga natija (rad etilsa xato matni bilan) va tasdiqlansa guruhdoshlarga 'jadval yangilandi'"""
    from app.bot.i18n import lang_of, t
    from app.bot.text_utils import esc

    out: List[Tuple[int, str]] = []
    student = await session.get(User, sub.user_id)
    if student:
        lang = lang_of(student)
        if approved:
            text = t(lang, "student_approved")
        elif reason:
            text = t(lang, "student_rejected_reason", reason=esc(reason))
        else:
            text = t(lang, "student_rejected")
        out.append((student.telegram_id, text))
    if approved and sub.group_id:
        group = await session.get(Group, sub.group_id)
        for member in await svc.group_members(session, sub.group_id):
            if student and member.id == student.id:
                continue
            out.append((member.telegram_id, t(lang_of(member), "group_schedule_updated", group=esc(group.name if group else ""))))
    return out


async def _send_all(bot, messages: List[Tuple[int, str]]) -> None:
    from app.bot.sender import safe_send

    for chat_id, text in messages:
        await safe_send(bot, chat_id, text, parse_mode="HTML")
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
    reason = (body.reason or "").strip()
    note = "Admin sayt orqali tasdiqlandi" if approved else ("Admin sayt orqali rad etildi" + (f": {reason}" if reason else ""))
    updated = await ScheduleService.review_submission(
        session, sub_id, reviewer.id if reviewer else None,
        ScheduleSubmissionReview(status=SubmissionStatus.APPROVED if approved else SubmissionStatus.REJECTED, admin_notes=note),
    )
    warning = updated.admin_notes if updated and updated.admin_notes and "⚠️" in updated.admin_notes else ""
    notified = 0
    bot = get_bot()
    if not warning and bot:
        messages = await _review_messages(session, sub, approved, reason)
        notified = len(messages)
        asyncio.create_task(_send_all(bot, messages))
    return {"status": updated.status.value, "warning": warning, "notified": notified, "submission": await svc.submission_detail(session, sub_id)}


# ---------------- xabarlar ----------------
@router.get("/broadcast/audiences")
async def audiences(uni: int = Query(0), admin=Admin, session: AsyncSession = Depends(get_db)):
    return await svc.audience_counts(session, await _uni(session, uni))


@router.get("/broadcast")
async def broadcast_history(uni: int = Query(0), audience: str = "", kind: str = Query("msg", pattern="^(msg|ad)$"),
                            admin=Admin, session: AsyncSession = Depends(get_db)):
    """Tanlangan auditoriyaga yuborilgan xabarlar tarixi; boshqa auditoriyaniki aralashmaydi"""
    if audience and audience not in svc.AUDIENCES:
        raise HTTPException(status_code=422, detail="Auditoriya noto'g'ri")
    return await svc.broadcast_history(session, await _uni(session, uni), audience, kind=kind)


@router.delete("/broadcast/{broadcast_id}")
async def delete_broadcast(broadcast_id: int, admin=Admin, session: AsyncSession = Depends(get_db)):
    """Xabar saytdan va foydalanuvchilarning botdagi chatidan o'chiriladi"""
    try:
        result = await svc.delete_broadcast(session, _bot(), broadcast_id)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not result:
        raise HTTPException(status_code=404, detail="Xabar topilmadi")
    logger.info(f"Admin site broadcast {broadcast_id} deleted by {admin['id']}: {result['to_delete']} chat messages")
    return result


class BroadcastIn(BaseModel):
    uni: int = 0
    audience: str
    kind: str = Field(default="msg", pattern="^(msg|ad)$")
    text: str = Field(min_length=1, max_length=4000)


@router.post("/broadcast")
async def broadcast(body: BroadcastIn, admin=Admin, session: AsyncSession = Depends(get_db)):
    await _uni(session, body.uni)
    if body.audience not in svc.AUDIENCES:
        raise HTTPException(status_code=422, detail="Auditoriya noto'g'ri")
    try:
        job = await svc.start_broadcast(session, _bot(), body.uni, body.audience, body.text.strip(), body.kind)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info(f"Admin site broadcast {job['id']} by {admin['id']}: {job['total']} recipients ({body.audience})")
    return job


@router.get("/broadcast/{broadcast_id}")
async def broadcast_status(broadcast_id: int, admin=Admin, session: AsyncSession = Depends(get_db)):
    job = await svc.broadcast_job(session, broadcast_id)
    if not job:
        raise HTTPException(status_code=404, detail="Topilmadi")
    return job
