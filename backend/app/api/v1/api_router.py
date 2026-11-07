from fastapi import APIRouter
from app.api.v1.ai import router as ai_router
from app.api.v1.announcements import router as announcements_router
from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.schedules import router as schedules_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.universities import router as universities_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(universities_router)
api_router.include_router(schedules_router)
api_router.include_router(tasks_router)
api_router.include_router(announcements_router)
api_router.include_router(ai_router)
