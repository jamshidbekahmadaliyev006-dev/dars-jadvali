"""
To'liq fan kodlarini (INS001-3, ELC013-L2) tiklaydi: oldingi backfill faqat asosiy kodni (INS001) yozgan, qo'shimcha
(-3, -L2: amaliyot/laboratoriya) yo'qolgan edi. Manba - eski baza nusxalari (backup-db-*.db): ularda talabalar yuborgan
jadvalning xom yozuvlari (schedule_submissions.ai_extracted_json) va nomi ichida kod qolgan eski fan nomlari bor.

    python scripts/recover_lesson_codes.py /path/to/backups        # nima o'zgarishini ko'rsatadi
    python scripts/recover_lesson_codes.py /path/to/backups --apply
Eng muhimi: kodi qo'shimchali (INS001-3) bo'lgan dars faqat ASOSIY kodga (INS001) tushib qolmasin, chunki qo'shimchasiz
kod ma'ruza, qo'shimchali kod amaliyot/laboratoriya degani.
"""
import asyncio
import glob
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from app.services.schedule_service import resolve_day_of_week, split_subject_code  # noqa: E402


def has_suffix(base, full) -> bool:
    return bool(base and full and full != base)


def harvest(path: str, by_slot: dict, by_schedule: dict) -> None:
    """Bitta baza nusxasidan: (guruh, kun, vaqt, asosiy kod) -> to'liq kod va dars_id -> to'liq kod"""
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        for group_id, js in db.execute("select group_id, ai_extracted_json from schedule_submissions order by id"):
            try:
                items = json.loads(js or "[]")
            except ValueError:
                continue
            for item in items if isinstance(items, list) else []:
                day = resolve_day_of_week(item.get("day"))
                _, base, full = split_subject_code(item.get("subject") or "")
                if group_id and day and base and full:
                    slot = (group_id, day.value, (item.get("start_time") or "").strip(), base)
                    if has_suffix(base, full) or slot not in by_slot:      # qo'shimchali yozuv ustun
                        by_slot[slot] = full
        try:
            for sid, name in db.execute("select sc.id, s.name from schedules sc join subjects s on s.id = sc.subject_id"):
                _, base, full = split_subject_code(name or "")
                if has_suffix(base, full):
                    by_schedule[sid] = full                                  # eski iflos fan nomi ichidagi kod
        except sqlite3.Error:
            pass
    finally:
        db.close()


async def main(folder: str, apply: bool) -> None:
    by_slot, by_schedule = {}, {}
    files = sorted(glob.glob(os.path.join(folder, "*.db")))
    for path in files:                    # eskidan yangiga
        harvest(path, by_slot, by_schedule)
    print(f"backups read: {len(files)}; slots with a code: {len(by_slot)}; "
          f"with a suffix: {sum(1 for k, v in by_slot.items() if has_suffix(k[3], v))}; from old subject names: {len(by_schedule)}")

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Schedule).options(selectinload(Schedule.subject)).where(Schedule.is_active == True)  # noqa: E712
        )).scalars().all()
        changed, kept = 0, 0
        for s in rows:
            base = s.subject.code if s.subject else None
            if not base:
                continue
            full = by_schedule.get(s.id) or by_slot.get((s.group_id, s.day_of_week.value, s.start_time, base))
            if has_suffix(base, full) and s.code != full:
                if changed < 12:
                    print(f"  lesson #{s.id} {s.subject.name}: {s.code} -> {full}")
                changed += 1
                if apply:
                    s.code = full
            else:
                kept += 1
        print(f"lessons that get the suffix back: {changed}; unchanged (no suffix known): {kept}")
        if apply:
            await session.commit()
            print("written")
        else:
            print("dry run: nothing written (use --apply)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--apply" in sys.argv))
    sys.stdout.flush()
    os._exit(0)
