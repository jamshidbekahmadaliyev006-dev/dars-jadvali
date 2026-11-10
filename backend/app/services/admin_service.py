"""
Admin sayt uchun ma'lumotlar. Hammasi bot ishlatadigan o'sha jadvallardan (users, groups, schedules,
schedule_submissions ...) to'g'ridan-to'g'ri hisoblanadi: sayt va bot doim bir xil narsani ko'radi.
Har bir ko'rsatkich tanlangan universitet bo'yicha.
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from sqlalchemy import and_, exists, func, or_, select, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.enums import SubmissionStatus, UserRole
from app.models.log import Announcement
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.services.schedule_service import (
    SCHEDULE_VIEW_CACHE,
    ScheduleService,
    clean_room_text,
    current_local_date,
    week_parity_for,
)

STAGES = ("done", "nosch", "nogr")
LESSON_KEYS = ("day", "start_time", "end_time", "subject", "room", "teacher", "week_parity", "lesson_type")
OPEN_STATUSES = (SubmissionStatus.ADMIN_REVIEW, SubmissionStatus.NEEDS_CORRECTION, SubmissionStatus.AI_COMPLETED)


def short_name(univ: University) -> str:
    """'Toshkent Axborot Texnologiyalari Universiteti' -> 'TATU'; qisqa nom bo'lsa o'sha"""
    if univ.short_name:
        return univ.short_name
    words = [w for w in (univ.name or "").split() if w[:1].isalpha()]
    if len(words) >= 2:
        return "".join(w[0] for w in words).upper()
    return univ.name


def _fmt(dt: Optional[datetime], pattern: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone(settings.TIMEZONE)).strftime(pattern)


def _has_schedule():
    return exists().where(Schedule.group_id == User.group_id, Schedule.is_active == True)


def _students(uni_id: int):
    return and_(User.university_id == uni_id, User.role == UserRole.USER)


# ---------------- universitetlar va bosh sahifa ----------------
async def list_universities(session: AsyncSession) -> List[Dict[str, Any]]:
    users = dict((await session.execute(
        select(User.university_id, func.count(User.id)).where(User.role == UserRole.USER).group_by(User.university_id)
    )).all())
    rows = (await session.execute(select(University).order_by(University.id))).scalars().all()
    items = [{"id": u.id, "name": u.name, "short": short_name(u), "users": users.get(u.id, 0)} for u in rows]
    items.sort(key=lambda x: (-x["users"], x["id"]))
    return items


async def overview(session: AsyncSession, uni_id: int) -> Dict[str, Any]:
    q = lambda stmt: session.scalar(stmt)
    users = await q(select(func.count(User.id)).where(_students(uni_id))) or 0
    with_sch = await q(select(func.count(User.id)).where(_students(uni_id), User.group_id.is_not(None), _has_schedule())) or 0
    no_group = await q(select(func.count(User.id)).where(_students(uni_id), User.group_id.is_(None))) or 0
    groups = await q(select(func.count(Group.id)).where(Group.university_id == uni_id)) or 0
    lessons = await q(select(func.count(Schedule.id)).where(Schedule.university_id == uni_id, Schedule.is_active == True)) or 0
    subjects = await q(select(func.count(func.distinct(Schedule.subject_id))).where(
        Schedule.university_id == uni_id, Schedule.is_active == True)) or 0

    req_status = {s.value if hasattr(s, "value") else s: n for s, n in (await session.execute(
        select(ScheduleSubmission.status, func.count(ScheduleSubmission.id))
        .where(ScheduleSubmission.university_id == uni_id).group_by(ScheduleSubmission.status)
    )).all()}
    lang = dict((await session.execute(
        select(User.language_code, func.count(User.id)).where(_students(uni_id)).group_by(User.language_code)
    )).all())
    top = [[name, n] for name, n in (await session.execute(
        select(Subject.name, func.count(Schedule.id).label("n"))
        .join(Subject, Subject.id == Schedule.subject_id)
        .where(Schedule.university_id == uni_id, Schedule.is_active == True)
        .group_by(Subject.id).order_by(func.count(Schedule.id).desc()).limit(5)
    )).all()]
    users_day = [[str(d), n] for d, n in (await session.execute(
        select(func.date(User.created_at), func.count(User.id)).where(_students(uni_id)).group_by(func.date(User.created_at))
    )).all() if d]
    req_day = [[str(d), n] for d, n in (await session.execute(
        select(func.date(ScheduleSubmission.created_at), func.count(ScheduleSubmission.id))
        .where(ScheduleSubmission.university_id == uni_id).group_by(func.date(ScheduleSubmission.created_at))
    )).all() if d]

    return {
        "users": users, "with_sch": with_sch, "no_group": no_group, "no_sch": users - with_sch - no_group,
        "groups": groups, "lessons": lessons, "subjects": subjects,
        "req_status": req_status, "lang": {k or "uz": v for k, v in lang.items()},
        "top": top, "users_day": sorted(users_day), "req_day": sorted(req_day),
    }


# ---------------- foydalanuvchilar ----------------
def _stage(group_id: Optional[int], has_schedule: bool) -> str:
    if not group_id:
        return "nogr"
    return "done" if has_schedule else "nosch"


def _user_row(user: User, group_name: Optional[str], faculty_name: Optional[str], has_schedule: bool) -> Dict[str, Any]:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "name": " ".join(x for x in (user.first_name, user.last_name) if x) or str(user.telegram_id),
        "username": user.username or "",
        "lang": user.language_code or "uz",
        "faculty": faculty_name or "",
        "group": group_name or "",
        "stage": _stage(user.group_id, has_schedule),
        "created": _fmt(user.created_at, "%d.%m.%Y"),
        "active": bool(user.is_active),
    }


async def list_users(
    session: AsyncSession, uni_id: int, q: str = "", stage: str = "", lang: str = "", page: int = 1, size: int = 20
) -> Dict[str, Any]:
    has = _has_schedule().label("has_schedule")
    stmt = (
        select(User, Group.name, Faculty.name, has)
        .outerjoin(Group, Group.id == User.group_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .where(_students(uni_id))
    )
    if stage == "done":
        stmt = stmt.where(User.group_id.is_not(None), _has_schedule())
    elif stage == "nosch":
        stmt = stmt.where(User.group_id.is_not(None), ~_has_schedule())
    elif stage == "nogr":
        stmt = stmt.where(User.group_id.is_(None))
    if lang:
        stmt = stmt.where(User.language_code == lang)
    text = (q or "").strip().lstrip("@")
    if text:
        like = f"%{text.lower()}%"
        stmt = stmt.where(or_(
            func.lower(User.first_name).like(like), func.lower(User.last_name).like(like),
            func.lower(User.username).like(like), cast(User.telegram_id, String).like(like),
            func.lower(Group.name).like(like), func.lower(Faculty.name).like(like),
        ))
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    size = max(1, min(size, 100))
    page = max(1, page)
    rows = (await session.execute(stmt.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * size).limit(size))).all()
    return {"total": total, "page": page, "size": size, "items": [_user_row(u, g, f, bool(h)) for u, g, f, h in rows]}


async def user_detail(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    has = _has_schedule().label("has_schedule")
    row = (await session.execute(
        select(User, Group.name, Faculty.name, has, University.name)
        .outerjoin(Group, Group.id == User.group_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .outerjoin(University, University.id == User.university_id)
        .where(User.id == user_id)
    )).first()
    if not row:
        return None
    user, group_name, faculty_name, has_schedule, univ_name = row
    data = _user_row(user, group_name, faculty_name, bool(has_schedule))
    data["university"] = univ_name or ""
    data["requests"] = await session.scalar(
        select(func.count(ScheduleSubmission.id)).where(ScheduleSubmission.user_id == user.id)) or 0
    data["is_admin"] = user.role == UserRole.ADMIN or settings.is_admin(user.telegram_id)
    return data


# ---------------- guruhlar ----------------
async def list_groups(session: AsyncSession, uni_id: int) -> List[Dict[str, Any]]:
    users_n = select(func.count(User.id)).where(User.group_id == Group.id, User.role == UserRole.USER).scalar_subquery()
    subj_n = select(func.count(func.distinct(Schedule.subject_id))).where(
        Schedule.group_id == Group.id, Schedule.is_active == True).scalar_subquery()
    lessons_n = select(func.count(Schedule.id)).where(Schedule.group_id == Group.id, Schedule.is_active == True).scalar_subquery()
    rows = (await session.execute(
        select(Group.id, Group.name, Faculty.name, users_n, subj_n, lessons_n)
        .join(Faculty, Faculty.id == Group.faculty_id)
        .where(Group.university_id == uni_id)
        .order_by(Faculty.name, Group.name)
    )).all()
    return [{"id": gid, "name": name, "faculty": fac, "users": u or 0, "subjects": s or 0, "lessons": l or 0}
            for gid, name, fac, u, s, l in rows]


async def group_members(session: AsyncSession, group_id: int) -> List[User]:
    return list((await session.execute(
        select(User).where(User.group_id == group_id, User.is_active == True, User.role == UserRole.USER)
    )).scalars().all())


# ---------------- jadval so'rovlari ----------------
def _lesson_out(item: Dict[str, Any]) -> Dict[str, Any]:
    """AI natijasidagi bitta dars -> saytda ko'rsatiladigan va tahrirlanadigan ko'rinish"""
    room = clean_room_text(item.get("room")).lstrip("-–— ").strip()
    building = clean_room_text(item.get("building")).rstrip("-–— ").strip()
    shown = f"{building}-{room}" if room and building and not room.lower().startswith(building.lower()) else room
    return {
        "day": item.get("day") or "",
        "start_time": (item.get("start_time") or "").strip(),
        "end_time": (item.get("end_time") or "").strip(),
        "subject": (item.get("subject") or "").strip(),
        "room": shown,
        "teacher": (item.get("teacher") or "").strip(),
        "week_parity": (item.get("week_parity") or "ALL").upper(),
        "lesson_type": (item.get("lesson_type") or "OTHER").upper(),
        "_b": item.get("building") or "",
        "_r": item.get("room") or "",
    }


def _lessons_of(sub: ScheduleSubmission) -> List[Dict[str, Any]]:
    try:
        raw = json.loads(sub.ai_extracted_json or "[]")
    except Exception:
        return []
    return [_lesson_out(i) for i in raw if isinstance(i, dict)]


async def list_submissions(session: AsyncSession, uni_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    rows = (await session.execute(
        select(ScheduleSubmission, Group.name, User.first_name, User.username)
        .outerjoin(Group, Group.id == ScheduleSubmission.group_id)
        .outerjoin(User, User.id == ScheduleSubmission.user_id)
        .where(ScheduleSubmission.university_id == uni_id)
        .order_by(ScheduleSubmission.id.desc()).limit(limit)
    )).all()
    out = []
    for sub, gname, first, uname in rows:
        out.append({
            "id": sub.id, "status": sub.status.value, "created": _fmt(sub.created_at, "%d.%m %H:%M"),
            "group": gname or "", "user": first or "", "username": uname or "",
            "lessons": len(_lessons_of(sub)), "open": sub.status in OPEN_STATUSES,
        })
    return out


async def submission_detail(session: AsyncSession, sub_id: int) -> Optional[Dict[str, Any]]:
    row = (await session.execute(
        select(ScheduleSubmission, Group.name, User.first_name, User.username)
        .outerjoin(Group, Group.id == ScheduleSubmission.group_id)
        .outerjoin(User, User.id == ScheduleSubmission.user_id)
        .where(ScheduleSubmission.id == sub_id)
    )).first()
    if not row:
        return None
    sub, gname, first, uname = row
    return {
        "id": sub.id, "status": sub.status.value, "created": _fmt(sub.created_at, "%d.%m.%Y %H:%M"),
        "group": gname or "", "group_id": sub.group_id, "user": first or "", "username": uname or "",
        "university_id": sub.university_id, "open": sub.status in OPEN_STATUSES,
        "lessons": _lessons_of(sub), "notes": sub.admin_notes or "",
    }


def _lesson_in(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Saytdan kelgan tahrirlangan dars -> AI natijasi formatidagi dars (bot shu formatni jadvalga yozadi)"""
    subject = str(item.get("subject") or "").strip()
    start = str(item.get("start_time") or "").strip()
    if not subject or not start:
        return None
    end = str(item.get("end_time") or "").strip()
    if not end:
        try:  # tugash vaqti berilmasa: 80 daqiqalik para
            h, m = (int(x) for x in start.split(":")[:2])
            total = h * 60 + m + 80
            end = f"{total // 60 % 24:02d}:{total % 60:02d}"
        except Exception:
            end = start
    shown = str(item.get("room") or "").strip()
    orig_b, orig_r = str(item.get("_b") or ""), str(item.get("_r") or "")
    if orig_r and _lesson_out({"room": orig_r, "building": orig_b})["room"] == shown:
        building, room = orig_b or None, orig_r  # xona o'zgarmagan - asl bino/xona saqlanadi
    else:
        building, room = None, shown or None
    parity = str(item.get("week_parity") or "ALL").upper()
    return {
        "day": str(item.get("day") or "").strip(), "subject": subject,
        "teacher": str(item.get("teacher") or "").strip() or None,
        "start_time": start, "end_time": end, "building": building, "room": room,
        "lesson_type": str(item.get("lesson_type") or "OTHER").upper(),
        "week_parity": parity if parity in ("ALL", "ODD", "EVEN") else "ALL",
    }


async def save_submission_lessons(session: AsyncSession, sub_id: int, lessons: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Admin tuzatgan darslarni saqlaydi. So'rov allaqachon tasdiqlangan bo'lsa, guruh jadvali ham shu
    zahoti qayta yoziladi - guruhdagi har bir talaba botda yangi jadvalni ko'radi.
    """
    sub = await session.get(ScheduleSubmission, sub_id)
    if not sub:
        raise LookupError("So'rov topilmadi")
    clean = [x for x in (_lesson_in(i) for i in lessons if isinstance(i, dict)) if x]
    sub.ai_extracted_json = json.dumps(clean, ensure_ascii=False)
    await session.commit()

    applied = 0
    if sub.status == SubmissionStatus.APPROVED and sub.group_id and clean:
        created = await ScheduleService.resolve_and_create_schedules_from_extraction(session, sub)
        applied = len(created)
    SCHEDULE_VIEW_CACHE.clear()
    return {"saved": len(clean), "applied": applied}


# ---------------- xabarlar ----------------
def audience_filter(uni_id: int, audience: str):
    base = and_(_students(uni_id), User.is_active == True)
    if audience == "nosch":
        return and_(base, User.group_id.is_not(None), ~_has_schedule())
    if audience == "done":
        return and_(base, User.group_id.is_not(None), _has_schedule())
    if audience == "nogr":
        return and_(base, User.group_id.is_(None))
    if audience in ("ru", "en", "uz"):
        return and_(base, User.language_code == audience)
    return base


AUDIENCES = ("all", "nosch", "done", "nogr", "ru", "en")


async def audience_counts(session: AsyncSession, uni_id: int) -> Dict[str, int]:
    return {a: await session.scalar(select(func.count(User.id)).where(audience_filter(uni_id, a))) or 0 for a in AUDIENCES}


async def audience_users(session: AsyncSession, uni_id: int, audience: str) -> List[User]:
    return list((await session.execute(select(User).where(audience_filter(uni_id, audience)))).scalars().all())


# Yuborish jarayonlari: e'lon ID -> holat. Server qayta ishga tushsa sanoq yo'qoladi, e'lon matni bazada qoladi.
BROADCASTS: Dict[int, Dict[str, Any]] = {}


async def run_broadcast(bot, announcement_id: int, recipients: List[tuple], text: str) -> None:
    from app.bot.sender import BLOCKED, NOT_STARTED, OK, safe_send

    job = BROADCASTS[announcement_id]
    for telegram_id in recipients:
        status, note = await safe_send(bot, telegram_id, text, parse_mode=None)  # admin matni HTML emas
        if status == OK:
            job["sent"] += 1
        elif status in (BLOCKED, NOT_STARTED):
            job["blocked"] += 1
        else:
            job["failed"] += 1
            logger.warning(f"Admin broadcast {announcement_id}: {telegram_id} {status} {note}")
        await asyncio.sleep(0.04)  # Telegram: sekundiga ~25 xabar
    job["done"] = True
    job["finished_at"] = time.time()


async def start_broadcast(session: AsyncSession, bot, uni_id: int, audience: str, text: str) -> Dict[str, Any]:
    users = await audience_users(session, uni_id, audience)
    ann = Announcement(university_id=uni_id, title=text[:100], content=text)
    session.add(ann)
    await session.commit()
    await session.refresh(ann)
    BROADCASTS[ann.id] = {"id": ann.id, "audience": audience, "total": len(users), "sent": 0, "blocked": 0,
                          "failed": 0, "done": False, "uni": uni_id}
    asyncio.create_task(run_broadcast(bot, ann.id, [u.telegram_id for u in users], text))
    return BROADCASTS[ann.id]


async def broadcast_history(session: AsyncSession, uni_id: int, limit: int = 30) -> List[Dict[str, Any]]:
    rows = (await session.execute(
        select(Announcement).where(Announcement.university_id == uni_id).order_by(Announcement.id.desc()).limit(limit)
    )).scalars().all()
    out = []
    for a in rows:
        job = BROADCASTS.get(a.id)
        out.append({"id": a.id, "text": a.content, "created": _fmt(a.created_at, "%d.%m %H:%M"),
                    "audience": job["audience"] if job else "", "total": job["total"] if job else None,
                    "sent": job["sent"] if job else None, "blocked": job["blocked"] if job else None,
                    "failed": job["failed"] if job else None, "done": job["done"] if job else True})
    return list(reversed(out))


def current_week() -> str:
    return week_parity_for(current_local_date()).value
