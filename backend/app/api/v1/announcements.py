from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.announcement import AnnouncementCreate, AnnouncementResponse, AnnouncementUpdate
from app.services.announcement_service import AnnouncementService

router = APIRouter(tags=["Announcements"])


@router.get("/announcements", response_model=List[AnnouncementResponse])
async def list_announcements(
    university_id: Optional[int] = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    target_univ = university_id or current_user.university_id
    if not target_univ:
        return []
    return await AnnouncementService.get_announcements_for_user(
        session=session,
        university_id=target_univ,
        group_id=current_user.group_id,
    )


@router.post("/announcements", response_model=AnnouncementResponse, status_code=status.HTTP_201_CREATED)
async def create_announcement(
    payload: AnnouncementCreate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    return await AnnouncementService.create_announcement(session, payload)


@router.put("/announcements/{announcement_id}", response_model=AnnouncementResponse)
async def update_announcement(
    announcement_id: int,
    payload: AnnouncementUpdate,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ann = await AnnouncementService.update_announcement(session, announcement_id, payload)
    if not ann:
        raise HTTPException(status_code=404, detail="E'lon topilmadi")
    return ann


@router.delete("/announcements/{announcement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_announcement(
    announcement_id: int,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ok = await AnnouncementService.delete_announcement(session, announcement_id)
    if not ok:
        raise HTTPException(status_code=404, detail="E'lon topilmadi")
    return None
