from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.enums import DayOfWeek, SubmissionStatus
from app.models.user import User
from app.schemas.schedule import (
    ReminderSettingResponse, ReminderSettingUpdate,
    ScheduleCreate, ScheduleDetailResponse, ScheduleResponse,
    ScheduleSubmissionCreate, ScheduleSubmissionResponse, ScheduleSubmissionReview,
    ScheduleUpdate,
)
from app.services.ai_service import AIService
from app.services.schedule_service import ScheduleService

router = APIRouter(tags=["Schedules & Submissions"])


# --- Schedules ---
@router.get("/schedules", response_model=List[ScheduleDetailResponse])
async def list_schedules(
    group_id: Optional[int] = Query(None),
    university_id: Optional[int] = Query(None),
    day_of_week: Optional[DayOfWeek] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dars jadvalini olish. Agar group_id berilmasa, talabaning o'z guruhidan olinadi.
    """
    target_group_id = group_id or current_user.group_id
    if not target_group_id and not university_id:
        return []
    return await ScheduleService.get_schedules(
        session=session,
        group_id=target_group_id,
        university_id=university_id or current_user.university_id,
        day_of_week=day_of_week,
    )


@router.post("/schedules", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await ScheduleService.create_schedule(session, payload)


@router.put("/schedules/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    sched = await ScheduleService.update_schedule(session, schedule_id, payload)
    if not sched:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    return sched


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(
    schedule_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ok = await ScheduleService.delete_schedule(session, schedule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Dars topilmadi")
    return None


# --- Reminder Settings ---
@router.get("/reminders/me", response_model=ReminderSettingResponse)
async def get_my_reminder_settings(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ScheduleService.get_or_create_reminder_setting(session, current_user.id)


@router.put("/reminders/me", response_model=ReminderSettingResponse)
async def update_my_reminder_settings(
    payload: ReminderSettingUpdate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await ScheduleService.update_reminder_setting(session, current_user.id, payload)


# --- Submissions & AI OCR ---
@router.post("/schedule-submissions", response_model=ScheduleSubmissionResponse, status_code=status.HTTP_201_CREATED)
async def submit_schedule_screenshot(
    university_id: int = Form(...),
    faculty_id: Optional[int] = Form(None),
    group_id: Optional[int] = Form(None),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dars jadvali screenshotini yuklash va AI orqali tahlilni boshlash.
    """
    contents = await file.read()
    payload = ScheduleSubmissionCreate(
        university_id=university_id,
        faculty_id=faculty_id,
        group_id=group_id,
        image_file_id=f"file_{int(file.size or 0)}_{file.filename}",
        image_url=file.filename,
    )
    submission = await ScheduleService.create_submission(session, current_user.id, payload)

    # AI tahlilini ishga tushirish
    processed_submission = await AIService.process_schedule_submission(
        session=session,
        submission_id=submission.id,
        image_bytes=contents,
        filename=file.filename or "schedule.jpg",
    )
    return processed_submission


@router.get("/schedule-submissions", response_model=List[ScheduleSubmissionResponse])
async def list_schedule_submissions(
    status_filter: Optional[SubmissionStatus] = Query(None, alias="status"),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Adminlar uchun barcha tekshirilishi kerak bo'lgan screenshotlar navbati"""
    return await ScheduleService.list_submissions(session, status=status_filter)


@router.post("/schedule-submissions/{submission_id}/review", response_model=ScheduleSubmissionResponse)
async def review_schedule_submission(
    submission_id: int,
    payload: ScheduleSubmissionReview,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Admin tomonidan AI natijasini tekshirish, tuzatish va jadvalni bazaga tasdiqlash"""
    sub = await ScheduleService.review_submission(session, submission_id, admin.id, payload)
    if not sub:
        raise HTTPException(status_code=404, detail="Submission topilmadi")
    return sub
