"""
Mavjud jadvallarga to'liq fan kodini (BGH001-3, PHY018-L2) yozadi: kod avval saqlanmagan edi.
Kod talabalar yuborgan jadval natijalaridan (schedule_submissions.ai_extracted_json) olinadi: har bir dars
(guruh, kun, vaqt, asosiy kod) bo'yicha eng oxirgi yozuv. Topilmasa fan kodi (asosiy) qoladi.

    python scripts/backfill_schedule_codes.py          # faqat nima o'zgarishini ko'rsatadi
    python scripts/backfill_schedule_codes.py --apply  # yozadi
"""
import asyncio
import json
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
            if apply and full and not s.code:
                s.code = full
        garbled = (await session.execute(select(Subject.id, Subject.name))).all()
        garbled = [(i, n) for i, n in garbled if re.search(r"[A-Z]{2,}\d{2,}", n or "")]
        print(f"active lessons: {len(rows)}; full code found: {exact}; only subject code: {fallback}; no code at all: {missing}")
        print(f"subjects whose NAME still contains a code (needs a look): {len(garbled)} {garbled[:8]}")
        if apply:
            await session.commit()
            print("written")
        else:
            print("dry run: nothing written (use --apply)")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
    os._exit(0)
