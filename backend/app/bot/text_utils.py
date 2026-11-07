from html import escape
from typing import Any, Dict, Iterable, List
from app.models.enums import DayOfWeek, WeekParity
from app.services.schedule_service import current_local_date, week_parity_for

DAY_LABELS_UZ = {
    DayOfWeek.MONDAY: "Dushanba",
    DayOfWeek.TUESDAY: "Seshanba",
    DayOfWeek.WEDNESDAY: "Chorshanba",
    DayOfWeek.THURSDAY: "Payshanba",
    DayOfWeek.FRIDAY: "Juma",
    DayOfWeek.SATURDAY: "Shanba",
    DayOfWeek.SUNDAY: "Yakshanba",
}


PARITY_LABELS_UZ = {
    WeekParity.ODD: "toq hafta",
    WeekParity.EVEN: "juft hafta",
}


def parity_suffix(schedule: Any) -> str:
    label = PARITY_LABELS_UZ.get(schedule.week_parity)
    return f" | {label}" if label else ""


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


def format_weekly_schedule(schedules: Iterable[Any]) -> str:
    """Guruhning barcha darslarini kunlar bo'yicha guruhlab, HTML matn qiladi"""
    by_day: Dict[DayOfWeek, List[Any]] = {}
    for s in schedules:
        by_day.setdefault(s.day_of_week, []).append(s)

    current_label = PARITY_LABELS_UZ[week_parity_for(current_local_date())]
    lines = [f"🗓 <b>Haftalik umumiy dars jadvali</b>\nHozir: {current_label}"]
    for day in DayOfWeek:
        day_schedules = by_day.get(day)
        if not day_schedules:
            continue
        day_schedules.sort(key=lambda s: s.start_time)
        lines.append(f"\n📌 <b>{DAY_LABELS_UZ[day]}</b>")
        for s in day_schedules:
            subj = esc(s.subject.name) if s.subject else "Fan"
            teacher = f" | {esc(s.teacher.full_name)}" if s.teacher else ""
            room = f" | {esc(s.room.number)}-xona" if s.room else ""
            lines.append(f"  ⏰ {esc(s.start_time)}-{esc(s.end_time)}: {subj}{room}{teacher}{parity_suffix(s)}")
    return "\n".join(lines)
