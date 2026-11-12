"""
"Mening rejalarim": foydalanuvchi muhim uchrashuv, kun tartibi, muddat va h.k. ni rasm yoki matn qilib yuboradi,
AI undan voqealarni ajratadi, bot vaqti kelganda eslatadi. Talaba bo'lmagan foydalanuvchilar ham foydalanadi.

Vaqt: foydalanuvchi Toshkent vaqti bilan yozadi; bazada naive UTC saqlanadi (loyihadagi boshqa jadvallar kabi).
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.task import PersonalEvent
from app.models.user import User
from app.services.ai_provider import get_ai_provider

MAX_EVENTS_PER_INPUT = 15
MAX_YEARS_AHEAD = 3
DEFAULT_HOUR = 9           # vaqti yozilmagan voqea uchun eslatma soati
DAILY_AI_LIMIT = 10        # bir foydalanuvchi kuniga nechta rasm/matn o'qittira oladi (AI limitini asrash uchun)

MONTHS = {
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
}
WEEKDAYS = {
    "uz": ["dushanba", "seshanba", "chorshanba", "payshanba", "juma", "shanba", "yakshanba"],
    "ru": ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}


@dataclass
class ParsedEvent:
    title: str
    day: date
    at: Optional[time]          # None - vaqt yozilmagan
    place: Optional[str] = None
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"title": self.title, "day": self.day.isoformat(), "at": self.at.strftime("%H:%M") if self.at else None,
                "place": self.place, "note": self.note}

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ParsedEvent":
        at = datetime.strptime(data["at"], "%H:%M").time() if data.get("at") else None
        return ParsedEvent(data["title"], date.fromisoformat(data["day"]), at, data.get("place"), data.get("note"))


def local_now() -> datetime:
    return datetime.now(pytz.timezone(settings.TIMEZONE))


def to_utc_naive(day: date, at: Optional[time]) -> datetime:
    tz = pytz.timezone(settings.TIMEZONE)
    local = tz.localize(datetime.combine(day, at or time(DEFAULT_HOUR, 0)))
    return local.astimezone(pytz.utc).replace(tzinfo=None)


def to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.timezone(settings.TIMEZONE))


def _clean(value: Any, limit: int) -> Optional[str]:
    text = " ".join(str(value).split()) if value not in (None, "", "null") else ""
    return text[:limit] or None


def validate_items(items: Any, today: date) -> List[ParsedEvent]:
    """AI javobidagi voqealarni tekshiradi: nomsiz, sanasiz, o'tib ketgan yoki bema'ni uzoq sanalar tashlanadi"""
    if isinstance(items, dict):
        items = items.get("events") or items.get("items") or []
    out: List[ParsedEvent] = []
    seen = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title"), 200)
        try:
            day = date.fromisoformat(str(item.get("date"))[:10])
        except ValueError:
            continue
        if not title or day < today or day > today.replace(year=today.year + MAX_YEARS_AHEAD):
            continue
        at = None
        raw = str(item.get("time") or "").strip()
        if raw:
            try:
                at = datetime.strptime(raw[:5], "%H:%M").time()
            except ValueError:
                at = None
        key = (title.lower(), day, at)
        if key in seen:
            continue
        seen.add(key)
        out.append(ParsedEvent(title, day, at, _clean(item.get("place"), 255), _clean(item.get("note"), 500)))
        if len(out) >= MAX_EVENTS_PER_INPUT:
            break
    out.sort(key=lambda e: (e.day, e.at or time(DEFAULT_HOUR)))
    return out


# ---------- AI limiti ----------
_AI_USES: Dict[int, Tuple[str, int]] = {}


def ai_allowed(user_id: int) -> bool:
    day, used = _AI_USES.get(user_id, ("", 0))
    return day != local_now().date().isoformat() or used < DAILY_AI_LIMIT


def ai_used(user_id: int) -> None:
    today = local_now().date().isoformat()
    day, used = _AI_USES.get(user_id, ("", 0))
    _AI_USES[user_id] = (today, used + 1 if day == today else 1)


class PlanService:
    @staticmethod
    async def read(images: Optional[List[bytes]], text: Optional[str]) -> List[ParsedEvent]:
        """Rasm(lar) yoki matndan voqealar. AI ishlamasa RuntimeError ko'tariladi (chaqiruvchi foydalanuvchiga aytadi)"""
        today = local_now().date()
        weekday = WEEKDAYS["en"][today.weekday()]
        raw = await get_ai_provider().extract_events(images or [], text or "", today.isoformat(), weekday)
        return validate_items(raw, today)

    @staticmethod
    async def add_events(session: AsyncSession, user: User, events: List[ParsedEvent]) -> int:
        """Saqlaydi; bir xil nom va vaqtli voqea ikki marta yozilmaydi. Nechta yangi qo'shilgani qaytadi"""
        existing = {(e.title.lower(), e.start_time) for e in (await session.execute(
            select(PersonalEvent).where(PersonalEvent.user_id == user.id))).scalars().all()}
        added = 0
        for ev in events:
            start = to_utc_naive(ev.day, ev.at)
            if (ev.title.lower(), start) in existing:
                continue
            session.add(PersonalEvent(
                user_id=user.id, title=ev.title, event_type="plan", description=ev.note, place=ev.place,
                start_time=start, has_time=ev.at is not None,
            ))
            added += 1
        await session.commit()
        return added

    @staticmethod
    async def upcoming(session: AsyncSession, user: User, limit: int = 20) -> List[PersonalEvent]:
        now = datetime.utcnow() - timedelta(hours=1)  # yangi boshlangan voqea ham bir soat ko'rinadi
        return list((await session.execute(
            select(PersonalEvent).where(PersonalEvent.user_id == user.id, PersonalEvent.start_time >= now)
            .order_by(PersonalEvent.start_time).limit(limit))).scalars().all())

    @staticmethod
    async def delete(session: AsyncSession, user: User, event_id: int) -> bool:
        ev = await session.get(PersonalEvent, event_id)
        if not ev or ev.user_id != user.id:
            return False
        await session.delete(ev)
        await session.commit()
        return True


def format_when(dt: datetime, has_time: bool, lang: str) -> str:
    """'15-noyabr, juma, 14:00'"""
    lang = lang if lang in MONTHS else "uz"
    local = to_local(dt)
    text = f"{local.day}-{MONTHS[lang][local.month - 1]}" if lang == "uz" else f"{local.day} {MONTHS[lang][local.month - 1]}"
    text += f", {WEEKDAYS[lang][local.weekday()]}"
    return text + (f", {local:%H:%M}" if has_time else "")


def reminder_due(ev: PersonalEvent, now_utc: datetime) -> Optional[str]:
    """Hozir qaysi eslatmani yuborish kerak: 'day' (1 kun oldin), 'soon' (1 soat oldin / vaqtsiz voqeada o'sha kuni) yoki None.
    O'tib ketgan eslatma yuborilmaydi (masalan voqea 3 soat qoldi deb qo'shilsa, 'ertaga' eslatmasi kerak emas)."""
    start = ev.start_time
    soon_at = start - timedelta(hours=1) if ev.has_time else start
    day_at = start - timedelta(days=1)
    # Eslatma o'z vaqtida yuboriladi; ancha kechikkan (masalan voqea 3 soat qoldi deb qo'shilgan) "ertaga" demaydi
    if not ev.remind2_sent and soon_at <= now_utc < (start if ev.has_time else start + timedelta(hours=8)):
        return "soon"
    if not ev.remind1_sent and day_at <= now_utc < day_at + timedelta(hours=2) and now_utc < soon_at:
        return "day"
    return None
