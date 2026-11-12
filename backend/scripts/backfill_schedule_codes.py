"""
Mavjud jadvallarga to'liq fan kodini (BGH001-3, PHY018-L2) yozadi: kod avval saqlanmagan edi.
Ikkinchi qadam: nomi ichida kod qolib ketgan fanlarni ("Elektronika va sxemalar-ELC013-L2") tozalaydi: kod alohida
ustunga o'tadi, nom toza bo'ladi, bir xil kodli va o'xshash nomli fan bo'lsa ularning darslari bittasiga birlashadi.
Kod talabalar yuborgan jadval natijalaridan (schedule_submissions.ai_extracted_json) olinadi: har bir dars
(guruh, kun, vaqt, asosiy kod) bo'yicha eng oxirgi yozuv. Topilmasa fan kodi (asosiy) qoladi.

    python scripts/backfill_schedule_codes.py          # faqat nima o'zgarishini ko'rsatadi
    python scripts/backfill_schedule_codes.py --apply  # yozadi
"""
import asyncio
import json
from difflib import SequenceMatcher
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.schedule import Schedule, ScheduleSubmission  # noqa: E402
from app.models.university import Subject  # noqa: E402
from app.services.schedule_service import resolve_day_of_week, split_subject_code  # noqa: E402
from app.services.university_service import name_key  # noqa: E402


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        full_by_key = {}
        subs = (await session.execute(select(ScheduleSubmission).order_by(ScheduleSubmission.id))).scalars().all()
        for sub in subs:
            try:
                lessons = json.loads(sub.ai_extracted_json or "[]")
            except ValueError:
                continue
            for item in lessons if isinstance(lessons, list) else []:
                day = resolve_day_of_week(item.get("day"))
                _, base, full = split_subject_code(item.get("subject") or "")
                if sub.group_id and day and base and full:
                    full_by_key[(sub.group_id, day, (item.get("start_time") or "").strip(), base)] = full

        rows = (await session.execute(
            select(Schedule).options(selectinload(Schedule.subject)).where(Schedule.is_active == True)  # noqa: E712
        )).scalars().all()
        exact = fallback = missing = 0
        for s in rows:
            base = s.subject.code if s.subject else None
            full = full_by_key.get((s.group_id, s.day_of_week, s.start_time, base)) if base else None
            if full:
                exact += 1
            elif base:
                full, fallback = base, fallback + 1
            else:
                missing += 1
            if apply and full and full != base and not s.code:   # faqat qo'shimchali TO'LIQ kod yoziladi; asosiy kod yozilmaydi
                s.code = full
        print(f"active lessons: {len(rows)}; full code found: {exact}; only subject code: {fallback}; no code at all: {missing}")

        # 2) nomi ichida kod qolgan fanlar
        subjects = (await session.execute(select(Subject))).scalars().all()
        garbled = [s for s in subjects if re.search(r"[A-Z]{2,}\d{2,}", s.name or "")]
        renamed = merged = 0
        done = {}  # (universitet, kod) -> tozalangan fan: o'sha kodli keyingi iflos fanlar unga birlashadi
        for s in garbled:
            clean, base, full = split_subject_code(s.name)
            if not base or clean == s.name:
                continue
            target = next((x for x in subjects if x.id != s.id and x.university_id == s.university_id and x.code == base
                           and x not in garbled and SequenceMatcher(None, name_key(clean), name_key(x.name)).ratio() >= 0.6), None)
            target = target or done.get((s.university_id, base))
            lessons = (await session.execute(select(Schedule).where(Schedule.subject_id == s.id))).scalars().all()
            print(f"  {s.name!r} -> {clean!r} [{base}]" + (f" merged into #{target.id} {target.name!r}" if target else " renamed") + f" ({len(lessons)} lessons)")
            if apply:
                for lesson in lessons:
                    if full and full != base:
                        lesson.code = full or lesson.code
                    if target:
                        lesson.subject_id = target.id
                if target:
                    await session.flush()
                    await session.delete(s)
                else:
                    s.name, s.code = clean, s.code or base
            if not target:
                done[(s.university_id, base)] = s
            merged += 1 if target else 0
            renamed += 0 if target else 1
        print(f"subjects with a code inside the name: {len(garbled)}; renamed: {renamed}; merged: {merged}")
        if apply:
            await session.commit()
            print("written")
        else:
            print("dry run: nothing written (use --apply)")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
    sys.stdout.flush()
    os._exit(0)
