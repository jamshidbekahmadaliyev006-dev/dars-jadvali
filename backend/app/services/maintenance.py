"""
Serverni yengil saqlash: keraksiz ma'lumotlar avtomatik o'chiriladi, kerakli narsalar qoladi.

QOLADI:  foydalanuvchilar, guruhlar, fanlar, faol darslar (schedules), o'qituvchilar va ularning jadvali,
         eslatma sozlamalari, kelgusi va yaqinda yuborilgan eslatmalar tarixi (30 kun).
O'CHADI: qaror qilingan jadvallarning rasm havolalari va AI xom natijasi, eski (nofaol) darslar,
         eski bildirishnoma va AI loglari, ochiq qolib ketgan eski so'rovlar.
Rasmlarning o'zi serverda hech qachon saqlanmaydi: ular Telegram'da turadi, bot ularni faqat
xotiraga yuklab AI'ga beradi.
"""
from datetime import datetime, timedelta
from typing import Dict
from sqlalchemy import delete, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.models.enums import SubmissionStatus
from app.models.log import AIProcessingLog, NotificationLog
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.teacher import TeacherLesson

LOG_RETENTION_DAYS = 30        # eslatma va AI loglari
DECIDED_KEEP_DAYS = 1          # qaror qilingan jadvalning xom natijasi shuncha kun turadi
STALE_OPEN_HOURS = 24          # shuncha vaqt "o'qilmoqda/kutmoqda" holatida qolgan so'rov yopiladi
INACTIVE_LESSON_DAYS = 14      # almashtirilgan eski darslar shuncha kundan keyin o'chadi


async def run_cleanup(session: AsyncSession, now: datetime = None) -> Dict[str, int]:
    now = now or datetime.utcnow()
    result: Dict[str, int] = {}

    def cutoff(**kw):
        return now - timedelta(**kw)

    decided = (SubmissionStatus.APPROVED, SubmissionStatus.REJECTED)

    # 1) Eski qaror qilingan so'rov yozuvlarining o'zi
    r = await session.execute(
        delete(ScheduleSubmission).where(
            ScheduleSubmission.status.in_(decided + (SubmissionStatus.NEEDS_CORRECTION,)),
            ScheduleSubmission.updated_at < cutoff(days=LOG_RETENTION_DAYS),
        )
    )
    result["old_submissions_deleted"] = r.rowcount or 0

    # 1) Qaror qilingan jadvallar: rasm havolasi va xom natija kerak emas
    r = await session.execute(
        update(ScheduleSubmission)
        .where(
            ScheduleSubmission.status.in_(decided),
            ScheduleSubmission.updated_at < cutoff(days=DECIDED_KEEP_DAYS),
            (ScheduleSubmission.ai_extracted_json.is_not(None)) | (ScheduleSubmission.image_url.is_not(None))
            | (ScheduleSubmission.image_file_id != "-"),
        )
        .values(ai_extracted_json=None, image_url=None, image_file_id="-", updated_at=ScheduleSubmission.updated_at)
    )
    result["submissions_stripped"] = r.rowcount or 0

    # 2) Ochiq qolib ketgan (AI qotgan / hech kim ko'rmagan) eski so'rovlar yopiladi
    r = await session.execute(
        update(ScheduleSubmission)
        .where(
            ScheduleSubmission.status.in_(
                (SubmissionStatus.PENDING, SubmissionStatus.AI_PROCESSING, SubmissionStatus.AI_COMPLETED)
            ),
            ScheduleSubmission.created_at < cutoff(hours=STALE_OPEN_HOURS),
        )
        .values(status=SubmissionStatus.NEEDS_CORRECTION, image_url=None, image_file_id="-", ai_extracted_json=None)
    )
    result["stale_closed"] = r.rowcount or 0

    # 4) Eski loglar
    r = await session.execute(delete(NotificationLog).where(NotificationLog.created_at < cutoff(days=LOG_RETENTION_DAYS)))
    result["notification_logs_deleted"] = r.rowcount or 0
    r = await session.execute(delete(AIProcessingLog).where(AIProcessingLog.created_at < cutoff(days=LOG_RETENTION_DAYS)))
    result["ai_logs_deleted"] = r.rowcount or 0

    # 5) Almashtirilgan (nofaol) eski darslar
    r = await session.execute(
        delete(Schedule).where(Schedule.is_active == False, Schedule.updated_at < cutoff(days=INACTIVE_LESSON_DAYS))
    )
    result["inactive_lessons_deleted"] = r.rowcount or 0
    r = await session.execute(
        delete(TeacherLesson).where(TeacherLesson.is_active == False, TeacherLesson.updated_at < cutoff(days=INACTIVE_LESSON_DAYS))
    )
    result["inactive_teacher_lessons_deleted"] = r.rowcount or 0

    await session.commit()

    # 6) SQLite faylini siqish (o'chirilgan joyni qaytarish)
    try:
        await session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
    except Exception:
        pass  # SQLite emas (masalan PostgreSQL) - kerak emas

    logger.info(f"Cleanup done: {result}")
    return result


async def cleanup_job() -> None:
    """Kuniga bir marta (03:30) ishga tushadi"""
    from app.core.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            await run_cleanup(session)
    except Exception as e:
        logger.error(f"Cleanup job failed: {type(e).__name__}: {e}")
