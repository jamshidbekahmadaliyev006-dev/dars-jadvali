from datetime import datetime
import math
import pytz
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.bot.bot_instance import get_bot
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.models.enums import DayOfWeek, NotificationType, WeekParity
from app.models.log import NotificationLog
from app.models.schedule import ReminderSetting, Schedule
from app.models.university import Group, Room
from app.models.user import User
from app.bot.i18n import lang_of
from app.bot.text_utils import format_reminder
from app.services.schedule_service import week_parity_for


async def check_and_send_lesson_reminders():
    """
    Har 60 soniyada ishga tushib, yaqinlashib kelayotgan darslar uchun talabalarga
    Telegram orqali avtomatik eslatma yuboruvchi scheduler vazifasi.
    """
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    weekday_idx = now.weekday()
    day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    today_enum = DayOfWeek[day_names[weekday_idx]]

    try:
        async with AsyncSessionLocal() as session:
            # Bugungi faol darslarni olish
            stmt = (
                select(Schedule)
                .options(
                    selectinload(Schedule.subject),
                    selectinload(Schedule.teacher),
                    selectinload(Schedule.group).selectinload(Group.university),
                    selectinload(Schedule.room).selectinload(Room.building),
                )
                .where(
                    Schedule.day_of_week == today_enum,
                    Schedule.is_active == True,
                    Schedule.week_parity.in_([WeekParity.ALL, week_parity_for(now.date())]),
                )
            )
            res = await session.execute(stmt)
            schedules = res.scalars().all()
            await _process_schedules(session, schedules, now)
    except Exception as e:
        # Vazifa ichidagi kutilmagan xatolik (masalan, DB vaqtincha mavjud emas) butun
        # schedulerni to'xtatib qo'ymasligi uchun shu yerda ushlab, log qilib qo'yamiz
        logger.error(f"check_and_send_lesson_reminders job failed: {e}")


async def _process_schedules(session: AsyncSession, schedules, now: datetime) -> None:
    """Berilgan darslar ro'yxati bo'yicha har bir talabaga eslatma yuborish kerakligini tekshiradi"""
    bot = get_bot()

    for sched in schedules:
        try:
            # Dars boshlanish vaqtini pars qilish (masalan "09:00")
            sched_h, sched_m = map(int, sched.start_time.split(":"))
            lesson_start_dt = now.replace(hour=sched_h, minute=sched_m, second=0, microsecond=0)

            # Dars o'tib ketgan bo'lsa o'tkazib yuborish
            time_diff = lesson_start_dt - now
            diff_minutes = int(time_diff.total_seconds() / 60)

            # Guruh talabalarini olish
            stmt_users = select(User).where(User.group_id == sched.group_id, User.is_active == True)
            res_users = await session.execute(stmt_users)
            students = res_users.scalars().all()

            for student in students:
                # Talabaning eslatma sozlamasini tekshirish
                stmt_setting = select(ReminderSetting).where(ReminderSetting.user_id == student.id)
                res_setting = await session.execute(stmt_setting)
                setting = res_setting.scalar_one_or_none()
                minutes_before = setting.minutes_before if setting else 15
                is_enabled = setting.is_enabled if setting else True

                if not is_enabled:
                    continue

                # Dars boshlanishiga aynan minutes_before oralig'i to'g'ri kelsa (masalan 14-16 min oraliqda)
                if 0 <= diff_minutes <= minutes_before:
                    # Takroriy yuborishni oldini olish
                    # created_at UTC'da saqlanadi. Sarlavha aniq solishtiriladi: bir kunda bir xil
                    # fan ikki marta bo'lsa yoki nomi boshqasining boshi bo'lsa, eslatma yo'qolmaydi.
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(pytz.utc)
                    log_title = f"Dars: {sched.subject.name if sched.subject else 'Fan nomi'} ({sched.start_time})"
                    stmt_log = select(NotificationLog.id).where(
                        NotificationLog.user_id == student.id,
                        NotificationLog.title == log_title,
                        NotificationLog.is_success == True,
                        NotificationLog.created_at >= today_start,
                    ).limit(1)
                    res_log = await session.execute(stmt_log)
                    already_sent = res_log.first()

                    if not already_sent:
                        # Sekundlar yaxlitlanadi, sozlamadan ko'p ko'rsatilmaydi
                        minutes_left = min(minutes_before, max(0, math.ceil(time_diff.total_seconds() / 60)))
                        msg_text = format_reminder(sched, minutes_left, lang_of(student))

                        sent_success = False
                        error_txt = None
                        if bot:
                            try:
                                await bot.send_message(
                                    chat_id=student.telegram_id,
                                    text=msg_text,
                                    parse_mode="HTML",
                                )
                                sent_success = True
                            except Exception as e:
                                error_txt = str(e)
                                logger.error(f"Failed to send reminder to {student.telegram_id}: {e}")
                        else:
                            # Mock / test muhitida muvaffaqiyatli deb qayd etiladi
                            sent_success = True

                        # Tarixga yozish
                        notif_log = NotificationLog(
                            user_id=student.id,
                            notification_type=NotificationType.LESSON_REMINDER,
                            title=log_title,
                            body=msg_text,
                            scheduled_for=lesson_start_dt,
                            sent_at=now,
                            is_success=sent_success,
                            error_message=error_txt,
                        )
                        session.add(notif_log)
                        await session.commit()
                        logger.info(f"Sent reminder for schedule {sched.id} to student {student.id}")
        except Exception as e:
            logger.error(f"Error checking schedule {sched.id}: {e}")
