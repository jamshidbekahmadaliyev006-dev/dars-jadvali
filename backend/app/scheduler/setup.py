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
    sched = get_scheduler()
    if not sched.running:
        sched.start()
        logger.info(f"APScheduler started with timezone: {settings.TIMEZONE}")


async def stop_scheduler() -> None:
    """Schedulerni xavfsiz to'xtatish"""
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped.")
