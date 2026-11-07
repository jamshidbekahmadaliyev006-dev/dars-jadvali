from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.ai import AIStudentAssistantRequest, AIStudentAssistantResponse
from app.services.ai_service import AIService

router = APIRouter(prefix="/ai", tags=["AI Student Assistant"])


@router.post("/assistant", response_model=AIStudentAssistantResponse)
async def ask_student_assistant(
    payload: AIStudentAssistantRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Talabaga o'z darslari, topshiriqlari va rejalari bo'yicha yordam beruvchi AI assistent.
    """
    return await AIService.ask_student_assistant(session, current_user, payload.query)
