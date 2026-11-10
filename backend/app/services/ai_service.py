from datetime import datetime
import json
import time
from typing import Any, Dict, List, Optional
import pytz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logging import logger
from app.models.enums import DayOfWeek, SubmissionStatus
from app.models.log import AIProcessingLog
from app.models.schedule import Schedule, ScheduleSubmission
from app.models.task import PersonalTask
from app.models.user import User
from app.schemas.ai import AIStudentAssistantResponse
from app.services.ai_provider import get_ai_provider


class AIService:
    @staticmethod
    async def process_schedule_submission(
        session: AsyncSession,
        submission_id: int,
        image_bytes: bytes,
        filename: str = "schedule.jpg",
        text: Optional[str] = None,
        images: Optional[List[bytes]] = None,
    ) -> ScheduleSubmission:
        """Talaba yuborgan screenshotni AI orqali tahlil qilish va navbatga qo'yish"""
        stmt = select(ScheduleSubmission).where(ScheduleSubmission.id == submission_id)
        result = await session.execute(stmt)
        submission = result.scalar_one_or_none()
        if not submission:
            raise ValueError(f"Submission with ID {submission_id} not found")

        submission.status = SubmissionStatus.AI_PROCESSING
        await session.commit()

        start_time = time.time()
        ai_provider = get_ai_provider()
        provider_name = type(ai_provider).__name__

        try:
            if text:
                extraction = await ai_provider.extract_schedule_from_text(text)
            elif images and len(images) > 1:
                extraction = await ai_provider.extract_schedule_from_images(images)
            else:
                extraction = await ai_provider.extract_schedule_from_image(image_bytes, filename)
            elapsed_ms = int((time.time() - start_time) * 1000)

            submission.ai_extracted_json = json.dumps(
                [lesson.model_dump() for lesson in extraction.lessons],
                ensure_ascii=False,
            )
            submission.ai_confidence = extraction.confidence
            submission.ai_warnings = extraction.warnings
            submission.status = SubmissionStatus.ADMIN_REVIEW

            # Log yozish
            ai_log = AIProcessingLog(
                submission_id=submission.id,
                provider_name=provider_name,
                processing_time_ms=elapsed_ms,
                status="SUCCESS",
            )
            session.add(ai_log)
            await session.commit()
            await session.refresh(submission)
            logger.info(f"AI extraction completed for submission {submission_id} in {elapsed_ms}ms")
            return submission
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            submission.status = SubmissionStatus.NEEDS_CORRECTION
            submission.ai_warnings = f"AI tahlil xatosi: {str(e)}"

            ai_log = AIProcessingLog(
                submission_id=submission.id,
                provider_name=provider_name,
                processing_time_ms=elapsed_ms,
                status="ERROR",
                error_details=str(e),
            )
            session.add(ai_log)
            await session.commit()
            await session.refresh(submission)
            logger.error(f"AI extraction failed for submission {submission_id}: {e}")
            return submission

    @staticmethod
    async def ask_student_assistant(
        session: AsyncSession,
        user: User,
        query: str,
    ) -> AIStudentAssistantResponse:
        """Talabaning joriy holati (darslar, vazifalar) asosida AI javob berish"""
        tz = pytz.timezone(settings.TIMEZONE)
        now = datetime.now(tz)
        weekday_idx = now.weekday()  # 0 = Monday
        day_names = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
        today_enum = DayOfWeek[day_names[weekday_idx]]
        tomorrow_enum = DayOfWeek[day_names[(weekday_idx + 1) % 7]]

        # Bugungi va ertangi darslarni olish
        today_lessons = []
        tomorrow_lessons = []
        if user.group_id:
            stmt_today = select(Schedule).where(
                Schedule.group_id == user.group_id,
                Schedule.day_of_week == today_enum,
                Schedule.is_active == True,
            ).order_by(Schedule.start_time.asc())
            res_today = await session.execute(stmt_today)
            for s in res_today.scalars().all():
                today_lessons.append({
                    "subject_name": s.subject.name if s.subject else "Noma'lum fan",
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "room_number": s.room.number if s.room else "Xona yo'q",
                    "lesson_type": s.lesson_type.value,
                })

            stmt_tomorrow = select(Schedule).where(
                Schedule.group_id == user.group_id,
                Schedule.day_of_week == tomorrow_enum,
                Schedule.is_active == True,
            ).order_by(Schedule.start_time.asc())
            res_tom = await session.execute(stmt_tomorrow)
            for s in res_tom.scalars().all():
                tomorrow_lessons.append({
                    "subject_name": s.subject.name if s.subject else "Noma'lum fan",
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "room_number": s.room.number if s.room else "Xona yo'q",
                })

        # Talabaning yaqin vazifalarini olish
        stmt_tasks = select(PersonalTask).where(
            PersonalTask.user_id == user.id,
            PersonalTask.is_completed == False,
        ).order_by(PersonalTask.due_date.asc()).limit(5)
        res_tasks = await session.execute(stmt_tasks)
        pending_tasks = [
            {"title": t.title, "priority": t.priority.value, "due_date": t.due_date.isoformat() if t.due_date else None}
            for t in res_tasks.scalars().all()
        ]

        context = {
            "student_name": user.first_name,
            "today_weekday": today_enum.value,
            "today_lessons": today_lessons,
            "tomorrow_lessons": tomorrow_lessons,
            "pending_tasks": pending_tasks,
        }

        ai_provider = get_ai_provider()
        answer = await ai_provider.chat_student_assistant(query, context)

        return AIStudentAssistantResponse(
            answer=answer,
            action_type="info",
            data={"today_lesson_count": len(today_lessons), "pending_task_count": len(pending_tasks)},
        )
