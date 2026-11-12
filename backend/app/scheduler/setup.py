from typing import Optional
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings
from app.core.logging import logger

scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is None:
        tz = pytz.timezone(settings.TIMEZONE)
        scheduler = AsyncIOScheduler(timezone=tz)
    return scheduler


async def start_scheduler() -> None:
    """Background task schedulerni ishga tushirish"""
    from app.scheduler.jobs import check_and_send_event_reminders, check_and_send_lesson_reminders

    sched = get_scheduler()
    if not sched.running:
        sched.add_job(
            check_and_send_lesson_reminders,
            "interval",
            seconds=60,
            id="lesson_reminders_job",
            replace_existing=True,
        )
        sched.add_job(
            check_and_send_event_reminders, "interval", seconds=60, id="event_reminders_job", replace_existing=True,
        )
        # Kuniga bir marta (Toshkent vaqti 03:30) keraksiz ma'lumotlarni tozalash
        from app.services.maintenance import cleanup_job
        sched.add_job(cleanup_job, "cron", hour=3, minute=30, id="daily_cleanup_job", replace_existing=True)
        sched.start()
        logger.info(f"APScheduler started with timezone: {settings.TIMEZONE} and 60s reminder interval.")


async def stop_scheduler() -> None:
    """Schedulerni xavfsiz to'xtatish"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
