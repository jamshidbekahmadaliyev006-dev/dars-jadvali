"""
Admin sayt uchun ma'lumotlar.

Hamma raqam botning "Statistika" va "Foydalanuvchilar" oynalaridagi bilan BIR XIL qoidalar bo'yicha
hisoblanadi (app/bot/handlers/admin_menu.py: collect_statistics, collect_user_counts), shuning uchun
sayt va bot doim bir xil son ko'rsatadi; testlar buni tekshiradi. `uni=0` - barcha universitetlar
(botdagi umumiy raqamlar), `uni>0` - faqat shu universitet.
"""
import asyncio
import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz
from sqlalchemy import String, and_, cast, exists, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.enums import SubmissionStatus, TeacherStatus, UserRole
from app.models.log import AdminBroadcast, Announcement
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.teacher import TeacherLesson, TeacherProfile
from app.models.university import Faculty, Group, Subject, University
from app.models.user import User
from app.services.schedule_service import (
    SCHEDULE_VIEW_CACHE,
    ScheduleService,
    clean_room_text,
    current_local_date,
    normalize_subject_name,
    week_parity_for,
)
from app.services.university_service import GENERAL_FACULTY_NAME, name_key

STAGES = ("done", "nosch", "nogr", "teacher", "pending", "students")
# Faqat ADMIN_REVIEW adminni kutadi (botdagi navbat ham shunday). NEEDS_CORRECTION - talaba tuzatib qayta yuborishi kerak.
OPEN_STATUSES = (SubmissionStatus.ADMIN_REVIEW,)


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


# ---------------- umumiy shartlar ----------------
def _scope(uni: int):
    """Foydalanuvchi shu universitetniki: o'zi tanlagan yoki o'qituvchi profili shu yerda"""
    if not uni:
        return true()
    return or_(
        User.university_id == uni,
        exists().where(TeacherProfile.user_id == User.id, TeacherProfile.university_id == uni),
    )


def _approved_ids():
    return select(TeacherProfile.user_id).where(TeacherProfile.status == TeacherStatus.APPROVED)


def _pending_ids():
    return select(TeacherProfile.user_id).where(TeacherProfile.status == TeacherStatus.PENDING)


def _is_student():
    """Botdagi qoida: guruhi bor va o'qituvchi (tasdiqlangan ham, kutayotgan ham) emas"""
    return and_(User.group_id.is_not(None), User.id.not_in(_approved_ids()), User.id.not_in(_pending_ids()))


def _has_schedule():
    return exists().where(Schedule.group_id == User.group_id, Schedule.is_active == True)


def _stage(user: User, has_schedule: bool, is_teacher: bool, is_pending: bool) -> str:
    if is_teacher:
        return "teacher"
    if is_pending:
        return "pending"
    if not user.group_id:
        return "nogr"
    return "done" if has_schedule else "nosch"


# ---------------- universitetlar ----------------
async def user_counts(session: AsyncSession, uni: int = 0, until: Optional[datetime] = None) -> Dict[str, int]:
    """Botning 'Foydalanuvchilar' oynasidagi 4 ta son (har bir foydalanuvchi bitta toifada)"""
    scope = and_(_scope(uni), User.created_at < until) if until else _scope(uni)
    q = lambda *where: session.scalar(select(func.count(User.id)).where(scope, *where))
    total = await q() or 0
    teachers = await q(User.id.in_(_approved_ids())) or 0
    pending = await q(User.id.in_(_pending_ids()), User.id.not_in(_approved_ids())) or 0
    students = await q(_is_student()) or 0
    return {"total": total, "teachers": teachers, "pending": pending, "students": students,
            "unregistered": total - teachers - pending - students}


async def statistics(session: AsyncSession, uni: int = 0, until: Optional[datetime] = None) -> Dict[str, int]:
    """Botning 'Statistika' oynasidagi sonlar (fanlar: guruhlardagi darslar emas, takrorlanmas fanlar)"""
    fac = select(func.count(Faculty.id)).where(Faculty.name != GENERAL_FACULTY_NAME)
    grp = select(func.count(Group.id))
    pairs = select(Subject.name, Subject.code).join(Schedule, Schedule.subject_id == Subject.id).where(Schedule.is_active == True)
    t_lessons = select(TeacherLesson.subject).where(TeacherLesson.is_active == True)
    lessons = select(func.count(Schedule.id)).where(Schedule.is_active == True)
    if until:
        fac = fac.where(Faculty.created_at < until)
        grp = grp.where(Group.created_at < until)
        pairs = pairs.where(Schedule.created_at < until)
        lessons = lessons.where(Schedule.created_at < until)
        t_lessons = t_lessons.where(TeacherLesson.created_at < until)
    if uni:
        fac = fac.where(Faculty.university_id == uni)
        grp = grp.where(Group.university_id == uni)
        pairs = pairs.where(Schedule.university_id == uni)
        lessons = lessons.where(Schedule.university_id == uni)
        t_lessons = t_lessons.join(TeacherProfile, TeacherProfile.id == TeacherLesson.teacher_id).where(
            TeacherProfile.university_id == uni)

    keys = {("c:" + code) if code else ("n:" + name_key(normalize_subject_name(name)[0]))
            for name, code in (await session.execute(pairs)).all() if name}
    for subject in (await session.execute(t_lessons)).scalars().all():
        clean, code = normalize_subject_name(subject or "")
        if clean:
            keys.add(("c:" + code) if code else ("n:" + name_key(clean)))
    return {
        "universities": 1 if uni else (await session.scalar(
            select(func.count(University.id)).where(University.created_at < until if until else true())) or 0),
        "faculties": await session.scalar(fac) or 0,
        "groups": await session.scalar(grp) or 0,
        "subjects": len(keys),
        "lessons": await session.scalar(lessons) or 0,
    }


async def list_universities(session: AsyncSession) -> List[Dict[str, Any]]:
    rows = (await session.execute(select(University).order_by(University.id))).scalars().all()
    items = []
    for u in rows:
        items.append({"id": u.id, "name": u.name, "short": short_name(u), "users": (await user_counts(session, u.id))["total"]})
    items.sort(key=lambda x: (-x["users"], x["id"]))
    return items


async def overview(session: AsyncSession, uni: int = 0, until: Optional[datetime] = None) -> Dict[str, Any]:
    """until - tanlangan sana oxiri (naive UTC): shu paytgacha bo'lgan holat. None - hozirgi holat (botdagi bilan bir xil)"""
    scope = and_(_scope(uni), User.created_at < until) if until else _scope(uni)
    subs = ScheduleSubmission.university_id == uni if uni else true()
    sched = Schedule.university_id == uni if uni else true()
    if until:
        subs = and_(subs, ScheduleSubmission.created_at < until)
        sched = and_(sched, Schedule.created_at < until)

    req_status = {s.value if hasattr(s, "value") else s: n for s, n in (await session.execute(
        select(ScheduleSubmission.status, func.count(ScheduleSubmission.id)).where(subs).group_by(ScheduleSubmission.status)
    )).all()}
    lang = dict((await session.execute(
        select(User.language_code, func.count(User.id)).where(scope).group_by(User.language_code)
    )).all())
    top = [[name, n] for name, n in (await session.execute(
        select(Subject.name, func.count(Schedule.id).label("n"))
        .join(Subject, Subject.id == Schedule.subject_id).where(sched, Schedule.is_active == True)
        .group_by(Subject.id).order_by(func.count(Schedule.id).desc(), Subject.name).limit(5)
    )).all()]
    users_day = [[str(d), n] for d, n in (await session.execute(
        select(func.date(User.created_at), func.count(User.id)).where(scope).group_by(func.date(User.created_at))
    )).all() if d]
    req_day = [[str(d), n] for d, n in (await session.execute(
        select(func.date(ScheduleSubmission.created_at), func.count(ScheduleSubmission.id))
        .where(subs).group_by(func.date(ScheduleSubmission.created_at))
    )).all() if d]
    return {
        **await user_counts(session, uni, until), **await statistics(session, uni, until),
        "req_status": req_status, "lang": {k or "uz": v for k, v in lang.items()},
        "top": top, "users_day": sorted(users_day), "req_day": sorted(req_day),
    }


def day_end_utc(day: str) -> Optional[datetime]:
    """'2026-11-09' -> o'sha kun tugagan payt (naive UTC). Bugun, kelajak yoki noto'g'ri sana -> None (hozirgi holat)"""
    from datetime import date, timedelta
    tz = pytz.timezone(settings.TIMEZONE)
    try:
        d = date.fromisoformat(day)
    except (TypeError, ValueError):
        return None
    if d >= datetime.now(tz).date():
        return None
    nxt = d + timedelta(days=1)
    return tz.localize(datetime(nxt.year, nxt.month, nxt.day)).astimezone(pytz.utc).replace(tzinfo=None)


async def activity(session: AsyncSession, uni: int, period: str, day: Optional[str]) -> Dict[str, Any]:
    """Tanlangan sana bo'yicha faollik: kun -> 24 soat, hafta -> 7 kun (dushanba-yakshanba), oy -> oyning kunlari.
    Vaqt Toshkent bo'yicha; bazada UTC saqlanadi."""
    import calendar
    from datetime import date, timedelta

    tz = pytz.timezone(settings.TIMEZONE)
    try:
        d = date.fromisoformat(day) if day else datetime.now(tz).date()
    except ValueError:
        d = datetime.now(tz).date()
    if period == "week":
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=7)
    elif period == "month":
        start = d.replace(day=1)
        end = (start + timedelta(days=calendar.monthrange(d.year, d.month)[1]))
    else:
        period, start, end = "day", d, d + timedelta(days=1)

    def to_utc(x: date) -> datetime:
        return tz.localize(datetime(x.year, x.month, x.day)).astimezone(pytz.utc).replace(tzinfo=None)

    lo, hi = to_utc(start), to_utc(end)
    if period == "day":
        n = 24
        labels = [f"{h:02d}:00" for h in range(n)]
        key = lambda dt: dt.hour
    elif period == "week":
        n = 7
        wd = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
        labels = [f"{wd[i]} {(start + timedelta(days=i)).day:02d}.{(start + timedelta(days=i)).month:02d}" for i in range(n)]
        key = lambda dt: (dt.date() - start).days
    else:
        # oy: haftalar bo'yicha (dushanba-yakshanba, oy chegarasi bilan kesilgan)
        last = end - timedelta(days=1)
        weeks, cur = [], start
        while cur <= last:
            stop = min(cur + timedelta(days=6 - cur.weekday()), last)
            weeks.append((cur, stop))
            cur = stop + timedelta(days=1)
        n = len(weeks)
        labels = [f"{a.day:02d}–{b.day:02d}.{a.month:02d}" for a, b in weeks]
        key = lambda dt: next((i for i, (a, b) in enumerate(weeks) if a <= dt.date() <= b), -1)

    def bucket(rows) -> List[int]:
        out = [0] * n
        for (created,) in rows:
            if created is None:
                continue
            local = pytz.utc.localize(created).astimezone(tz)
            i = key(local)
            if 0 <= i < n:
                out[i] += 1
        return out

    users = bucket((await session.execute(
        select(User.created_at).where(_scope(uni), User.created_at >= lo, User.created_at < hi))).all())
    reqs = bucket((await session.execute(
        select(ScheduleSubmission.created_at).where(
            ScheduleSubmission.university_id == uni if uni else true(),
            ScheduleSubmission.created_at >= lo, ScheduleSubmission.created_at < hi))).all())
    return {"period": period, "start": start.isoformat(), "end": (end - timedelta(days=1)).isoformat(),
            "labels": labels, "users": users, "reqs": reqs, "total_users": sum(users), "total_reqs": sum(reqs)}


# ---------------- foydalanuvchilar ----------------
def _user_row(user: User, group_name: Optional[str], faculty_name: Optional[str], univ: Optional[University],
              has_schedule: bool, is_teacher: bool, is_pending: bool) -> Dict[str, Any]:
    return {
        "id": user.id,
        "telegram_id": user.telegram_id,
        "name": " ".join(x for x in (user.first_name, user.last_name) if x) or str(user.telegram_id),
        "username": user.username or "",
        "lang": user.language_code or "uz",
        "univ": short_name(univ) if univ else "",
        "faculty": faculty_name or "",
        "group": group_name or "",
        "stage": _stage(user, has_schedule, is_teacher, is_pending),
        "created": _fmt(user.created_at, "%d.%m.%Y"),
        "active": bool(user.is_active),
        "is_admin": user.role == UserRole.ADMIN or settings.is_admin(user.telegram_id),
    }


def _user_select():
    teacher = User.id.in_(_approved_ids()).label("is_teacher")
    pending = and_(User.id.in_(_pending_ids()), User.id.not_in(_approved_ids())).label("is_pending")
    return (
        select(User, Group.name, Faculty.name, University, _has_schedule().label("has_schedule"), teacher, pending)
        .outerjoin(Group, Group.id == User.group_id)
        .outerjoin(Faculty, Faculty.id == User.faculty_id)
        .outerjoin(University, University.id == User.university_id)
    )


async def list_users(
    session: AsyncSession, uni: int = 0, q: str = "", stage: str = "", lang: str = "", page: int = 1, size: int = 20
) -> Dict[str, Any]:
    stmt = _user_select().where(_scope(uni))
    if stage == "teacher":
        stmt = stmt.where(User.id.in_(_approved_ids()))
    elif stage == "pending":
        stmt = stmt.where(User.id.in_(_pending_ids()), User.id.not_in(_approved_ids()))
    elif stage == "students":
        stmt = stmt.where(_is_student())
    elif stage == "done":
        stmt = stmt.where(_is_student(), _has_schedule())
    elif stage == "nosch":
        stmt = stmt.where(_is_student(), ~_has_schedule())
    elif stage == "nogr":
        stmt = stmt.where(User.group_id.is_(None), User.id.not_in(_approved_ids()), User.id.not_in(_pending_ids()))
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
    return {"total": total, "page": page, "size": size,
            "items": [_user_row(u, g, f, un, bool(h), bool(t), bool(p)) for u, g, f, un, h, t, p in rows]}


async def user_detail(session: AsyncSession, user_id: int) -> Optional[Dict[str, Any]]:
    row = (await session.execute(_user_select().where(User.id == user_id))).first()
    if not row:
        return None
    user, group_name, faculty_name, univ, has_schedule, is_teacher, is_pending = row
    data = _user_row(user, group_name, faculty_name, univ, bool(has_schedule), bool(is_teacher), bool(is_pending))
    data["university"] = univ.name if univ else ""
    data["requests"] = await session.scalar(
        select(func.count(ScheduleSubmission.id)).where(ScheduleSubmission.user_id == user.id)) or 0
    return data


# ---------------- guruhlar ----------------
async def list_groups(session: AsyncSession, uni: int = 0) -> List[Dict[str, Any]]:
    users_n = select(func.count(User.id)).where(User.group_id == Group.id, User.role == UserRole.USER).scalar_subquery()
    subj_n = select(func.count(func.distinct(Schedule.subject_id))).where(
        Schedule.group_id == Group.id, Schedule.is_active == True).scalar_subquery()
    lessons_n = select(func.count(Schedule.id)).where(Schedule.group_id == Group.id, Schedule.is_active == True).scalar_subquery()
    stmt = (
        select(Group.id, Group.name, Faculty.name, University, users_n, subj_n, lessons_n)
        .join(Faculty, Faculty.id == Group.faculty_id)
        .join(University, University.id == Group.university_id)
        .order_by(University.id, Faculty.name, Group.name)
    )
    if uni:
        stmt = stmt.where(Group.university_id == uni)
    rows = (await session.execute(stmt)).all()
    return [{"id": gid, "name": name, "faculty": fac, "univ": short_name(univ), "users": u or 0, "subjects": s or 0, "lessons": l or 0}
            for gid, name, fac, univ, u, s, l in rows]


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


def _sub_select():
    return (
        select(ScheduleSubmission, Group.name, User.first_name, User.username, University)
        .outerjoin(Group, Group.id == ScheduleSubmission.group_id)
        .outerjoin(User, User.id == ScheduleSubmission.user_id)
        .outerjoin(University, University.id == ScheduleSubmission.university_id)
    )


async def list_submissions(session: AsyncSession, uni: int = 0, statuses: Optional[List[SubmissionStatus]] = None,
                           limit: int = 50) -> List[Dict[str, Any]]:
    stmt = _sub_select()
    if uni:
        stmt = stmt.where(ScheduleSubmission.university_id == uni)
    if statuses:
        stmt = stmt.where(ScheduleSubmission.status.in_(statuses))
    rows = (await session.execute(stmt.order_by(ScheduleSubmission.id.desc()).limit(max(1, min(limit, 200))))).all()
    return [{
        "id": sub.id, "status": sub.status.value, "created": _fmt(sub.created_at, "%d.%m %H:%M"),
        "group": gname or "", "univ": short_name(univ) if univ else "", "user": first or "", "username": uname or "",
        "lessons": len(_lessons_of(sub)), "open": sub.status in OPEN_STATUSES,
    } for sub, gname, first, uname, univ in rows]


async def submission_detail(session: AsyncSession, sub_id: int) -> Optional[Dict[str, Any]]:
    row = (await session.execute(_sub_select().where(ScheduleSubmission.id == sub_id))).first()
    if not row:
        return None
    sub, gname, first, uname, univ = row
    return {
        "id": sub.id, "status": sub.status.value, "created": _fmt(sub.created_at, "%d.%m.%Y %H:%M"),
        "group": gname or "", "group_id": sub.group_id, "univ": short_name(univ) if univ else "",
        "user": first or "", "username": uname or "",
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
    zahoti qayta yoziladi: guruhdagi har bir talaba botda yangi jadvalni ko'radi.
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
AUDIENCES = ("all", "nosch", "done", "nogr", "teachers", "ru", "en")


def audience_filter(uni: int, audience: str):
    base = and_(_scope(uni), User.role == UserRole.USER, User.is_active == True)
    student = and_(base, _is_student())
    if audience == "nosch":
        return and_(student, ~_has_schedule())
    if audience == "done":
        return and_(student, _has_schedule())
    if audience == "nogr":
        return and_(base, User.group_id.is_(None), User.id.not_in(_approved_ids()), User.id.not_in(_pending_ids()))
    if audience == "teachers":
        return and_(base, User.id.in_(_approved_ids()))
    if audience in ("ru", "en", "uz"):
        return and_(base, User.language_code == audience)
    return base


async def audience_counts(session: AsyncSession, uni: int = 0) -> Dict[str, int]:
    return {a: await session.scalar(select(func.count(User.id)).where(audience_filter(uni, a))) or 0 for a in AUDIENCES}


async def audience_users(session: AsyncSession, uni: int, audience: str) -> List[User]:
    return list((await session.execute(select(User).where(audience_filter(uni, audience)))).scalars().all())


# Yuborish jarayonlari: jonli hisob xotirada (tez yangilanadi), natija bazada (admin_broadcasts) saqlanadi,
# shuning uchun server qayta ishga tushsa ham tarix va sanoq yo'qolmaydi.
BROADCASTS: Dict[int, Dict[str, Any]] = {}
SESSION_FACTORY = AsyncSessionLocal


async def _save_progress(job: Dict[str, Any]) -> None:
    async with SESSION_FACTORY() as s:
        row = await s.get(AdminBroadcast, job["id"])
        if row:
            row.sent, row.blocked, row.failed, row.is_done = job["sent"], job["blocked"], job["failed"], job["done"]
            if job["done"]:
                row.finished_at = datetime.now(pytz.utc)
            await s.commit()


async def run_broadcast(bot, broadcast_id: int, recipients: List[int], text: str) -> None:
    from app.bot.sender import BLOCKED, NOT_STARTED, OK, safe_send

    job = BROADCASTS[broadcast_id]
    try:
        for index, telegram_id in enumerate(recipients, start=1):
            status, note = await safe_send(bot, telegram_id, text, parse_mode=None)  # admin matni HTML emas
            if status == OK:
                job["sent"] += 1
            elif status in (BLOCKED, NOT_STARTED):
                job["blocked"] += 1
            else:
                job["failed"] += 1
                logger.warning(f"Admin broadcast {broadcast_id}: {telegram_id} {status} {note}")
            if index % 10 == 0:
                await _save_progress(job)
            await asyncio.sleep(0.04)  # Telegram: sekundiga ~25 xabar
    finally:
        job["done"] = True
        job["finished_at"] = time.time()
        try:
            await _save_progress(job)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Admin broadcast {broadcast_id}: could not save the result: {e}")


async def start_broadcast(session: AsyncSession, bot, uni: int, audience: str, text: str) -> Dict[str, Any]:
    users = await audience_users(session, uni, audience)
    univ_id = uni or await session.scalar(select(University.id).order_by(University.id).limit(1))
    if not univ_id:
        raise ValueError("Universitet yo'q")
    row = AdminBroadcast(university_id=uni, audience=audience, text=text, total=len(users))
    session.add(Announcement(university_id=univ_id, title=text[:100], content=text))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    BROADCASTS[row.id] = {"id": row.id, "audience": audience, "total": len(users), "sent": 0, "blocked": 0,
                          "failed": 0, "done": False, "uni": uni}
    asyncio.create_task(run_broadcast(bot, row.id, [u.telegram_id for u in users], text))
    return BROADCASTS[row.id]


def _broadcast_out(row: AdminBroadcast) -> Dict[str, Any]:
    job = BROADCASTS.get(row.id)  # yuborilayotgan bo'lsa jonli hisob
    return {"id": row.id, "text": row.text, "created": _fmt(row.created_at, "%d.%m %H:%M"), "audience": row.audience,
            "total": row.total, "sent": job["sent"] if job else row.sent, "blocked": job["blocked"] if job else row.blocked,
            "failed": job["failed"] if job else row.failed, "done": job["done"] if job else bool(row.is_done)}


async def broadcast_history(session: AsyncSession, uni: int = 0, audience: str = "", limit: int = 30) -> List[Dict[str, Any]]:
    """Tanlangan universitet va AUDITORIYA uchun yuborilgan xabarlar (boshqa auditoriyaniki ko'rinmaydi)"""
    stmt = select(AdminBroadcast).where(AdminBroadcast.university_id == uni)
    if audience:
        stmt = stmt.where(AdminBroadcast.audience == audience)
    rows = (await session.execute(stmt.order_by(AdminBroadcast.id.desc()).limit(limit))).scalars().all()
    return [_broadcast_out(r) for r in reversed(rows)]


async def broadcast_job(session: AsyncSession, broadcast_id: int) -> Optional[Dict[str, Any]]:
    row = await session.get(AdminBroadcast, broadcast_id)
    return {**_broadcast_out(row), "uni": row.university_id} if row else None


# ---------------- bildirishnomalar (qo'ng'iroqcha) ----------------
async def notifications(session: AsyncSession, since: int = 0, limit: int = 15) -> Dict[str, Any]:
    """Yangi qo'shilgan foydalanuvchilar (har bir odam alohida) va admin ko'rib chiqishi kerak so'rovlar soni"""
    student = User.role == UserRole.USER
    latest = await session.scalar(select(func.max(User.id)).where(student)) or 0
    new = (await session.scalar(select(func.count(User.id)).where(student, User.id > since)) or 0) if since else 0
    rows = (await session.execute(_user_select().where(student).order_by(User.id.desc()).limit(limit))).all()
    items = [{"id": u.id, "name": " ".join(x for x in (u.first_name, u.last_name) if x) or str(u.telegram_id),
              "username": u.username or "", "univ": short_name(un) if un else "", "lang": u.language_code or "uz",
              "created": _fmt(u.created_at, "%d.%m %H:%M")} for u, g, f, un, h, t, p in rows]
    review = await session.scalar(select(func.count(ScheduleSubmission.id)).where(
        ScheduleSubmission.status.in_(OPEN_STATUSES))) or 0
    return {"latest": latest, "new": new, "items": items, "review": review}


def current_week() -> str:
    return week_parity_for(current_local_date()).value
