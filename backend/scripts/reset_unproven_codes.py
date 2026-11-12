"""
Mavjud darslarning faqat asosiy kodi (INS001, qo'shimchasiz) o'chiriladi: dars faqat nomi bilan ko'rinadi. Qo'shimchali
to'liq kodlar (INS001-3, ELC013-L2) qoladi. Sabab: qo'shimchasi noma'lum kod hamma darsni ma'ruza qilib ko'rsatardi;
yangi yuborilgan jadvallar esa kodni qo'shimchasi bilan saqlaydi.
`--keep-proven`: eski nusxalar jadvalda aynan shunday yozilganini isbotlagan oddiy kodlar ham qolsin.

    python scripts/reset_unproven_codes.py /path/to/backups          # ko'rsatadi
    python scripts/reset_unproven_codes.py /path/to/backups --apply
"""
import asyncio
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.schedule import Schedule  # noqa: E402
from scripts.recover_lesson_codes import harvest  # noqa: E402


async def main(folder: str, apply: bool, keep_proven: bool = False) -> None:
    by_slot, by_schedule = {}, {}
    for path in sorted(glob.glob(os.path.join(folder, "*.db"))):
        harvest(path, by_slot, by_schedule)
    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Schedule).options(selectinload(Schedule.subject)).where(Schedule.is_active == True)  # noqa: E712
        )).scalars().all()
        reset = kept_proven = kept_suffix = 0
        for s in rows:
            base = s.subject.code if s.subject else None
            if not s.code:
                continue
            if s.code != base:
                kept_suffix += 1                      # qo'shimchali to'liq kod
            elif keep_proven and by_slot.get((s.group_id, s.day_of_week.value, s.start_time, base)) == base:
                kept_proven += 1                      # jadvalning o'zida shunday yozilgan
            else:
                reset += 1
                if apply:
                    s.code = None
        print(f"with a suffix (kept): {kept_suffix}; plain code proven by a real timetable (kept): {kept_proven}; "
              f"base code without suffix (back to name only): {reset}")
        if apply:
            await session.commit()
            print("written")
        else:
            print("dry run: nothing written (use --apply)")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], "--apply" in sys.argv, "--keep-proven" in sys.argv))
    sys.stdout.flush()
    os._exit(0)
