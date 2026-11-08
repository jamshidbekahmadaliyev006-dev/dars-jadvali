from html import escape
from typing import Any, Dict, Iterable, List, Sequence
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


def format_reminder(schedule: Any, minutes_left: int, lang: str = DEFAULT_LANG) -> str:
    if minutes_left > 0:
        header = t(lang, "reminder_in", time=format_minutes(minutes_left, lang))
    else:
        header = t(lang, "reminder_now")

    lines = [
        header,
        "",
        f"📚 {esc(schedule.subject.name) if schedule.subject else '—'}",
        f"🕒 {esc(schedule.start_time)}",
    ]
    if schedule.room:
        lines.append(f"📍 {esc(schedule.room.number)}")
    if schedule.teacher:
        lines.append(f"👤 {esc(schedule.teacher.full_name)}")
    return "\n".join(lines)
