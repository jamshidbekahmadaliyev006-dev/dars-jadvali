from datetime import date
from html import escape
from typing import Any, Dict, Iterable, List, Optional, Sequence
from app.bot.i18n import (
    DAY_LABELS,
    DEFAULT_LANG,
    PARITY_LABELS,
    format_counts,
    format_lesson_count,
    format_minutes,
    t,
)
from app.models.enums import DayOfWeek
from app.services.schedule_service import current_local_date, week_parity_for


def _minutes(value: str) -> int:
    try:
        hours, minutes = str(value).split(":")[:2]
        return int(hours) * 60 + int(minutes)
    except Exception:
        return -1


def schedule_issues(lessons: Sequence[Dict[str, Any]], lang: str = DEFAULT_LANG, from_image: bool = True) -> List[str]:
    """
    AI o'qigan jadvaldagi shubhali joylar: talabaga aniq aytamiz - qaysi dars, qanday kamchilik.
    """
    from app.services.schedule_service import resolve_day_of_week

    issues: List[str] = []
    no_building = [i for i in lessons if i.get("room") and not i.get("building")] if from_image else []
    # Bino ko'p darsda yo'q bo'lsa - har birini sanab o'tirmay, bitta qatorda aytamiz
    group_building = len(no_building) > 3
    if group_building:
        rooms = sorted({str(i.get("room")) for i in no_building})
        issues.append("• " + t(lang, "issue_building_many", n=len(no_building), rooms=esc(", ".join(rooms[:8]))))
    for item in lessons:
        day = item.get("day") or "?"
        start = item.get("start_time") or ""
        subject = (item.get("subject") or "?")[:40]
        label = f"{esc(day)} {esc(start)} — {esc(subject)}"
        problems = []
        if not resolve_day_of_week(item.get("day")):
            problems.append(t(lang, "issue_day"))
        if _minutes(start) < 0 or _minutes(item.get("end_time") or "") < 0:
            problems.append(t(lang, "issue_time"))
        elif _minutes(item.get("end_time")) <= _minutes(start):
            problems.append(t(lang, "issue_time_order"))
        if not item.get("room"):
            problems.append(t(lang, "issue_room"))
        elif from_image and not item.get("building") and not group_building:
            problems.append(t(lang, "issue_building"))
        if problems:
            issues.append(f"• {label}: {', '.join(problems)}")

    # Bir kunda, bir hafta turida vaqti ustma-ust tushgan turli darslar
    seen = sorted(
        (i for i in lessons if _minutes(i.get("start_time") or "") >= 0 and _minutes(i.get("end_time") or "") >= 0),
        key=lambda i: (str(i.get("day")), _minutes(i.get("start_time"))),
    )
    for a, b in zip(seen, seen[1:]):
        same_slot = a.get("day") == b.get("day")
        parity_clash = "ALL" in (a.get("week_parity"), b.get("week_parity")) or a.get("week_parity") == b.get("week_parity")
        if same_slot and parity_clash and _minutes(b.get("start_time")) < _minutes(a.get("end_time")):
            issues.append(
                f"• {esc(a.get('day'))} {esc(b.get('start_time'))}: "
                + t(lang, "issue_overlap", a=esc((a.get("subject") or "?")[:30]), b=esc((b.get("subject") or "?")[:30]))
            )
    return issues


async def show_typing(message: Any) -> None:
    """'yozmoqda...' animatsiyasi - faqat bezak, xato bo'lsa asosiy ish to'xtamasligi kerak"""
    try:
        await message.bot.send_chat_action(message.chat.id, "typing")
    except Exception:
        pass


def esc(value: Any) -> str:
    """
    Telegram parse_mode='HTML' xabarlariga qo'yiladigan har qanday foydalanuvchi yoki AI
    tomonidan taqdim etilgan matnni xavfsiz tarzda escape qiladi (masalan talabaning ismi,
    username'i, o'zi yozgan universitet/fakultet/guruh nomi, AI o'qigan fan/o'qituvchi nomi).
    Shu orqali HTML teglari (<a>, <b> va h.k.) orqali xabar formatini buzish yoki boshqa
    foydalanuvchilarni/adminni aldovchi havolalar joylashtirish oldi olinadi.
    """
    if value is None:
        return ""
    return escape(str(value), quote=False)


def subject_names(schedules: Iterable[Any]) -> List[str]:
    """Takrorlanmaydigan fan nomlari, alifbo tartibida"""
    return sorted({s.subject.name for s in schedules if s.subject})


def schedule_summary(schedules: Sequence[Any], lang: str = DEFAULT_LANG) -> str:
    return format_counts(len(subject_names(schedules)), len(schedules), lang)


def _lesson_line(s: Any, lang: str, show_parity: bool = False) -> str:
    # Faqat boshlanish vaqti: rasmlarda tugash vaqti yozilmaydi, AI uni taxmin qiladi
    parts = [f"<b>{esc(s.start_time)}</b> — {esc(s.subject.name) if s.subject else '—'}"]
    if s.room:
        parts.append(esc(s.room.number))
    if s.teacher:
        parts.append(esc(s.teacher.full_name))
    if show_parity and s.week_parity in PARITY_LABELS[lang]:
        parts.append(PARITY_LABELS[lang][s.week_parity])
    return " · ".join(parts)


def format_day_schedule(icon: str, title: str, schedules: Sequence[Any], lang: str = DEFAULT_LANG) -> str:
    if not schedules:
        return f"{icon} <b>{title}</b>\n\n{t(lang, 'day_empty')}"
    lines = [f"{icon} <b>{title}</b> — {format_lesson_count(len(schedules), lang)}\n"]
    lines.extend(_lesson_line(s, lang) for s in schedules)
    return "\n".join(lines)


def format_weekly_schedule(schedules: Sequence[Any], lang: str = DEFAULT_LANG) -> str:
    """Guruhning barcha darslarini kunlar bo'yicha guruhlab, HTML matn qiladi"""
    by_day: Dict[DayOfWeek, List[Any]] = {}
    for s in schedules:
        by_day.setdefault(s.day_of_week, []).append(s)

    current_parity = week_parity_for(current_local_date())
    lines = [
        t(lang, "week_title"),
        t(lang, "week_today", date=format_date(current_local_date(), lang, with_year=True)),
        schedule_summary(schedules, lang),
        t(lang, "week_now", parity=PARITY_LABELS[lang][current_parity]),
    ]
    for day in DayOfWeek:
        day_schedules = by_day.get(day)
        if not day_schedules:
            continue
        day_schedules.sort(key=lambda s: s.start_time)
        lines.append(f"\n<b>{DAY_LABELS[lang][day]}</b>")
        lines.extend(_lesson_line(s, lang, show_parity=True) for s in day_schedules)
    return "\n".join(lines)


_MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June",
           "July", "August", "September", "October", "November", "December"],
    "uz": ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
           "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"],
    "ru": ["января", "февраля", "марта", "апреля", "мая", "июня",
           "июля", "августа", "сентября", "октября", "ноября", "декабря"],
}


def format_date(value: date, lang: str = DEFAULT_LANG, with_year: bool = False) -> str:
    """9-noyabr, Dushanba  /  9 ноября, Понедельник (with_year: 9-noyabr 2026, Dushanba)"""
    lang = lang if lang in _MONTHS else DEFAULT_LANG
    month = _MONTHS[lang][value.month - 1]
    weekday = DAY_LABELS[lang][list(DayOfWeek)[value.weekday()]]
    year = f" {value.year}" if with_year else ""
    if lang == "ru":
        return f"{value.day} {month}{year}, {weekday}"
    if lang == "en":
        return f"{weekday}, {month} {value.day}{year}"
    return f"{value.day}-{month}{year}, {weekday}"


def format_reminder(
    schedule: Any, minutes_left: int, lang: str = DEFAULT_LANG, lesson_date: Optional[date] = None
) -> str:
    if minutes_left > 0:
        header = t(lang, "reminder_in", time=format_minutes(minutes_left, lang))
    else:
        header = t(lang, "reminder_now")

    end = f"–{esc(schedule.end_time)}" if getattr(schedule, "end_time", None) else ""
    lines = [
        header,
        "",
        f"📅 {format_date(lesson_date or current_local_date(), lang, with_year=True)}",
        f"📚 {esc(schedule.subject.name) if schedule.subject else '—'}",
        f"🕒 {esc(schedule.start_time)}{end}",
    ]
    if schedule.room:
        lines.append(f"📍 {esc(schedule.room.number)}")
    if schedule.teacher:
        lines.append(f"👤 {esc(schedule.teacher.full_name)}")
    return "\n".join(lines)


# --- O'qituvchi jadvali ---
def _teacher_line(lesson: Any, lang: str, show_parity: bool = False) -> str:
    parts = [f"<b>{esc(lesson.start_time)}–{esc(lesson.end_time)}</b> — {esc(lesson.subject)}"]
    if lesson.group_name:
        parts.append(f"👥 {esc(lesson.group_name)}")
    if lesson.room:
        parts.append(f"📍 {esc(lesson.room)}")
    if show_parity and lesson.week_parity in PARITY_LABELS[lang]:
        parts.append(PARITY_LABELS[lang][lesson.week_parity])
    return " · ".join(parts)


def format_teacher_day(icon: str, title: str, lessons: Sequence[Any], lang: str = DEFAULT_LANG) -> str:
    if not lessons:
        return f"{icon} <b>{title}</b>\n\n{t(lang, 'day_empty')}"
    lines = [f"{icon} <b>{title}</b> — {format_lesson_count(len(lessons), lang)}\n"]
    lines.extend(_teacher_line(l, lang) for l in lessons)
    return "\n".join(lines)


def format_teacher_week(lessons: Sequence[Any], lang: str = DEFAULT_LANG) -> str:
    groups = sorted({l.group_name for l in lessons if l.group_name})
    current_parity = week_parity_for(current_local_date())
    lines = [
        t(lang, "teacher_week_title"),
        t(lang, "week_today", date=format_date(current_local_date(), lang, with_year=True)),
        t(lang, "teacher_week_summary", lessons=format_lesson_count(len(lessons), lang), groups=len(groups)),
        t(lang, "week_now", parity=PARITY_LABELS[lang][current_parity]),
    ]
    by_day: Dict[DayOfWeek, List[Any]] = {}
    for lesson in lessons:
        by_day.setdefault(lesson.day_of_week, []).append(lesson)
    for day in DayOfWeek:
        if by_day.get(day):
            lines.append(f"\n<b>{DAY_LABELS[lang][day]}</b>")
            lines.extend(_teacher_line(l, lang, show_parity=True) for l in sorted(by_day[day], key=lambda l: l.start_time))
    return "\n".join(lines)


def format_teacher_reminder(lesson: Any, minutes_left: int, lang: str, lesson_date: date) -> str:
    header = t(lang, "reminder_in", time=format_minutes(minutes_left, lang)) if minutes_left > 0 else t(lang, "reminder_now")
    lines = [
        header,
        "",
        f"📅 {format_date(lesson_date, lang, with_year=True)}",
        f"📚 {esc(lesson.subject)}",
        f"🕒 {esc(lesson.start_time)}–{esc(lesson.end_time)}",
    ]
    if lesson.group_name:
        lines.append(f"👥 {esc(lesson.group_name)}")
    if lesson.room:
        lines.append(f"📍 {esc(lesson.room)}")
    return "\n".join(lines)



import re as _re

_TIME_TOKEN = _re.compile(r"(?<!\d)([01]?\d|2[0-3])[:.][0-5]\d(?!\d)")
MIN_TEXT_SCHEDULE_LESSONS = 3


def looks_like_full_schedule(text: str) -> bool:
    """
    Qo'lda yozilgan matn jadvalga o'xshaydimi: kamida 3 ta darsga yetarli (har bir dars qatorida vaqt bor).
    "Dushanba matematika" kabi bir-ikki qator yoki oddiy gap jadval deb qabul qilinmaydi.
    """
    lines = [ln for ln in (text or "").splitlines() if ln.strip()]
    with_time = sum(1 for ln in lines if _TIME_TOKEN.search(ln))
    if with_time < MIN_TEXT_SCHEDULE_LESSONS and len(lines) <= 1:
        # Bitta uzun qator ichida ";" yoki "," bilan ajratilgan darslar
        with_time = len(_TIME_TOKEN.findall(text or "")) // 2
    return with_time >= MIN_TEXT_SCHEDULE_LESSONS
