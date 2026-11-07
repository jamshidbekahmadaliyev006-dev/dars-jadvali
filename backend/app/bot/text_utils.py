from html import escape
from typing import Any, Dict, Iterable, List
from app.models.enums import DayOfWeek

DAY_LABELS_UZ = {
    DayOfWeek.MONDAY: "Dushanba",
    DayOfWeek.TUESDAY: "Seshanba",
    DayOfWeek.WEDNESDAY: "Chorshanba",
    DayOfWeek.THURSDAY: "Payshanba",
    DayOfWeek.FRIDAY: "Juma",
    DayOfWeek.SATURDAY: "Shanba",
    DayOfWeek.SUNDAY: "Yakshanba",
}


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

    lines = ["🗓 <b>Haftalik umumiy dars jadvali:</b>"]
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
            lines.append(f"  ⏰ {esc(s.start_time)}-{esc(s.end_time)}: {subj}{room}{teacher}")
    return "\n".join(lines)
