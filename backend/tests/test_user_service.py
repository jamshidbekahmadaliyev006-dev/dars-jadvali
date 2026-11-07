import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.enums import UserRole
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_get_or_create_regular_user(db_session: AsyncSession):
    tg_id = 123000456
    # Bu ID ADMIN_IDS da yo'q
    assert not settings.is_admin(tg_id)

    user, created = await UserService.get_or_create_user(
        session=db_session,
        telegram_id=tg_id,
        first_name="Bekzod",
        last_name="Toshmatov",
        username="bekzod_t",
    )
    assert created is True
    assert user.role == UserRole.USER
    assert user.first_name == "Bekzod"

    # Ikkinchi marta chaqirilganda qayta yaratilmasligi kerak
    same_user, created_second = await UserService.get_or_create_user(
        session=db_session,
        telegram_id=tg_id,
        first_name="Bekzod (Updated)",
    )
    assert created_second is False
    assert same_user.id == user.id
    assert same_user.first_name == "Bekzod (Updated)"


@pytest.mark.asyncio
async def test_get_or_create_admin_user(db_session: AsyncSession):
    # ADMIN_IDS dan bitta ID olish
    admin_id = settings.admin_id_list[0] if settings.admin_id_list else 123456789
    
    # settings.is_admin true ekanligiga ishonch hosil qilish
    settings.ADMIN_IDS_RAW = str(admin_id)

    user, created = await UserService.get_or_create_user(
        session=db_session,
        telegram_id=admin_id,
        first_name="Asosiy Admin",
    )
    assert user.role == UserRole.ADMIN


@pytest.mark.asyncio
async def test_update_user_role(db_session: AsyncSession):
    user, _ = await UserService.get_or_create_user(
        session=db_session,
        telegram_id=777111222,
        first_name="Oddiy Talaba",
    )
    assert user.role == UserRole.USER

    # Admin tomonidan rolni o'zgartirish
    updated = await UserService.update_role(db_session, user.id, UserRole.ADMIN)
    assert updated.role == UserRole.ADMIN
