import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.enums import SubmissionStatus, UserRole
from app.models.user import User
from app.schemas.schedule import ScheduleSubmissionCreate
from app.services.ai_service import AIService
from app.services.schedule_service import ScheduleService


@pytest.mark.asyncio
async def test_ai_schedule_extraction_and_assistant(db_session: AsyncSession):
    student = User(telegram_id=888777666, first_name="Nodir", role=UserRole.USER, university_id=1)
    db_session.add(student)
    await db_session.commit()

    # 1. Submission yaratish
    sub = await ScheduleService.create_submission(
        db_session,
        student.id,
        ScheduleSubmissionCreate(university_id=1, image_file_id="tg_photo_1"),
    )

    # 2. AI tahlilini ishga tushirish (Mock provider orqali)
    processed = await AIService.process_schedule_submission(
        session=db_session,
        submission_id=sub.id,
        image_bytes=b"dummy_image_data",
        filename="schedule.png",
    )
    assert processed.status == SubmissionStatus.ADMIN_REVIEW
    assert processed.ai_extracted_json is not None
    assert "Kompyuter tarmoqlari" in processed.ai_extracted_json

    # 3. AI Student Assistant
    res_assistant = await AIService.ask_student_assistant(
        session=db_session,
        user=student,
        query="Bugun qanday darslarim bor?",
    )
    assert res_assistant.answer is not None
    assert len(res_assistant.answer) > 0
