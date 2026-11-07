from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UserRoleUpdate
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserResponse)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
):
    """Joriy autentifikatsiyadan o'tgan foydalanuvchi profilini olish"""
    return current_user


@router.get("", response_model=List[UserResponse])
async def list_all_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Barcha foydalanuvchilar ro'yxati (Faqat Administratorlar uchun)"""
    users = await UserService.list_users(session, skip=skip, limit=limit)
    return users


@router.patch("/{user_id}/role", response_model=UserResponse)
async def change_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Foydalanuvchi rolini o'zgartirish (Faqat Administratorlar uchun)"""
    updated_user = await UserService.update_role(session, user_id, payload.role)
    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Foydalanuvchi topilmadi",
        )
    return updated_user
