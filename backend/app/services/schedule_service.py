from datetime import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.enums import DayOfWeek, LessonType, SubmissionStatus
from app.models.schedule import ReminderSetting, Schedule, ScheduleSubmission
from app.schemas.schedule import ReminderSettingUpdate, ScheduleCreate, ScheduleSubmissionCreate, ScheduleSubmissionReview, ScheduleUpdate


class ScheduleService:
    @staticmethod
    async def get_schedules(
        session: AsyncSession,
        group_id: Optional[int] = None,
        university_id: Optional[int] = None,
        day_of_week: Optional[DayOfWeek] = None,
    ) -> List[Schedule]:
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.subject),
                selectinload(Schedule.teacher),
                selectinload(Schedule.room),
                selectinload(Schedule.group),
            )
            .where(Schedule.is_active == True)
        )
        if group_id:
            stmt = stmt.where(Schedule.group_id == group_id)
        if university_id:
            stmt = stmt.where(Schedule.university_id == university_id)
        if day_of_week:
            stmt = stmt.where(Schedule.day_of_week == day_of_week)

        stmt = stmt.order_by(Schedule.day_of_week.asc(), Schedule.start_time.asc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_schedule_by_id(session: AsyncSession, schedule_id: int) -> Optional[Schedule]:
        stmt = (
            select(Schedule)
            .options(
                selectinload(Schedule.subject),
                selectinload(Schedule.teacher),
                selectinload(Schedule.room),
                selectinload(Schedule.group),
            )
            .where(Schedule.id == schedule_id)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_schedule(session: AsyncSession, payload: ScheduleCreate) -> Schedule:
        schedule = Schedule(**payload.model_dump())
        session.add(schedule)
        await session.commit()
        await session.refresh(schedule)
        return schedule

    @staticmethod
    async def update_schedule(session: AsyncSession, schedule_id: int, payload: ScheduleUpdate) -> Optional[Schedule]:
        sched = await ScheduleService.get_schedule_by_id(session, schedule_id)
        if not sched:
            return None
        for k, v in payload.model_dump(exclude_unset=True).items():
            setattr(sched, k, v)
        await session.commit()
        await session.refresh(sched)
        return sched

    @staticmethod
    async def delete_schedule(session: AsyncSession, schedule_id: int) -> bool:
        sched = await ScheduleService.get_schedule_by_id(session, schedule_id)
        if not sched:
            return False
        await session.delete(sched)
        await session.commit()
        return True

    # --- Reminder Settings ---
    @staticmethod
    async def get_or_create_reminder_setting(session: AsyncSession, user_id: int) -> ReminderSetting:
        stmt = select(ReminderSetting).where(ReminderSetting.user_id == user_id)
        result = await session.execute(stmt)
        setting = result.scalar_one_or_none()
        if not setting:
            setting = ReminderSetting(user_id=user_id, is_enabled=True, minutes_before=15)
            session.add(setting)
            await session.commit()
            await session.refresh(setting)
        return setting

    @staticmethod
    async def update_reminder_setting(session: AsyncSession, user_id: int, payload: ReminderSettingUpdate) -> ReminderSetting:
        setting = await ScheduleService.get_or_create_reminder_setting(session, user_id)
        setting.is_enabled = payload.is_enabled
        setting.minutes_before = payload.minutes_before
        await session.commit()
        await session.refresh(setting)
        return setting

    # --- Submissions (Workflow) ---
    @staticmethod
    async def create_submission(session: AsyncSession, user_id: int, payload: ScheduleSubmissionCreate) -> ScheduleSubmission:
        submission = ScheduleSubmission(
            user_id=user_id,
            university_id=payload.university_id,
            faculty_id=payload.faculty_id,
            group_id=payload.group_id,
            image_file_id=payload.image_file_id,
            image_url=payload.image_url,
            status=SubmissionStatus.PENDING,
        )
        session.add(submission)
        await session.commit()
        await session.refresh(submission)
        return submission

    @staticmethod
    async def list_submissions(
        session: AsyncSession,
        status: Optional[SubmissionStatus] = None,
        university_id: Optional[int] = None,
    ) -> List[ScheduleSubmission]:
        stmt = select(ScheduleSubmission)
        if status:
            stmt = stmt.where(ScheduleSubmission.status == status)
        if university_id:
            stmt = stmt.where(ScheduleSubmission.university_id == university_id)
        stmt = stmt.order_by(ScheduleSubmission.id.desc())
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_submission_by_id(session: AsyncSession, submission_id: int) -> Optional[ScheduleSubmission]:
        stmt = select(ScheduleSubmission).where(ScheduleSubmission.id == submission_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def review_submission(
        session: AsyncSession,
        submission_id: int,
        reviewer_id: int,
        review: ScheduleSubmissionReview,
    ) -> Optional[ScheduleSubmission]:
        submission = await ScheduleService.get_submission_by_id(session, submission_id)
        if not submission:
            return None

        submission.status = review.status
        submission.reviewer_id = reviewer_id
        submission.admin_notes = review.admin_notes

        # Agar APPROVED bo'lsa va tasdiqlangan darslar mavjud bo'lsa, ularni bazaga saqlash
        if review.status == SubmissionStatus.APPROVED and review.approved_schedules and submission.group_id:
            for item in review.approved_schedules:
                day_str = item.get("day_of_week", "MONDAY").upper()
                day_enum = DayOfWeek[day_str] if day_str in DayOfWeek.__members__ else DayOfWeek.MONDAY
                lesson_type_str = item.get("lesson_type", "LECTURE").upper()
                lesson_type_enum = LessonType[lesson_type_str] if lesson_type_str in LessonType.__members__ else LessonType.LECTURE

                sched = Schedule(
                    university_id=submission.university_id,
                    group_id=submission.group_id,
                    subject_id=item["subject_id"],
                    teacher_id=item.get("teacher_id"),
                    room_id=item.get("room_id"),
                    day_of_week=day_enum,
                    start_time=item["start_time"],
                    end_time=item["end_time"],
                    lesson_type=lesson_type_enum,
                )
                session.add(sched)

        await session.commit()
        await session.refresh(submission)
        return submission
