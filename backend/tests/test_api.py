import pytest
from httpx import AsyncClient
from app.core.config import settings
from app.models.enums import UserRole
from app.models.user import User
from tests.test_auth import generate_valid_tg_init_data


@pytest.mark.asyncio
async def test_health_endpoints(async_client: AsyncClient):
    # Root
    res_root = await async_client.get("/")
    assert res_root.status_code == 200
    assert res_root.json()["status"] == "running"

    # API v1 health
    res_health = await async_client.get("/api/v1/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "ok"
    assert data["database_connected"] is True


@pytest.mark.asyncio
async def test_unauthorized_access(async_client: AsyncClient):
    # Tokensiz profilga kirish
    res = await async_client.get("/api/v1/users/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_profile(
    async_client: AsyncClient,
    test_student_user: User,
    student_auth_headers: dict,
):
    res = await async_client.get("/api/v1/users/me", headers=student_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["telegram_id"] == test_student_user.telegram_id
    assert data["role"] == "USER"


@pytest.mark.asyncio
async def test_role_based_access_control(
    async_client: AsyncClient,
    student_auth_headers: dict,
    admin_auth_headers: dict,
    test_student_user: User,
):
    # 1. Oddiy talaba /api/v1/users ga kira olmaydi (403 Forbidden)
    res_forbidden = await async_client.get("/api/v1/users", headers=student_auth_headers)
    assert res_forbidden.status_code == 403

    # 2. Administrator barcha foydalanuvchilar ro'yxatiga kira oladi (200 OK)
    res_admin = await async_client.get("/api/v1/users", headers=admin_auth_headers)
    assert res_admin.status_code == 200
    assert isinstance(res_admin.json(), list)

    # 3. Oddiy talaba rol o'zgartira olmaydi (403 Forbidden)
    res_role_fail = await async_client.patch(
        f"/api/v1/users/{test_student_user.id}/role",
        json={"role": "ADMIN"},
        headers=student_auth_headers,
    )
    assert res_role_fail.status_code == 403

    # 4. Administrator rol o'zgartira oladi (200 OK)
    res_role_ok = await async_client.patch(
        f"/api/v1/users/{test_student_user.id}/role",
        json={"role": "ADMIN"},
        headers=admin_auth_headers,
    )
    assert res_role_ok.status_code == 200
    assert res_role_ok.json()["role"] == "ADMIN"


@pytest.mark.asyncio
async def test_telegram_webapp_auth_endpoint(async_client: AsyncClient):
    token = settings.BOT_TOKEN
    user_info = {
        "id": 999111333,
        "first_name": "Farrux",
        "username": "farrux_tg",
    }
    valid_init_data = generate_valid_tg_init_data(token, user_info)

    # To'g'ri initData
    res = await async_client.post(
        "/api/v1/auth/telegram-webapp",
        json={"init_data": valid_init_data},
    )
    assert res.status_code == 200
    body = res.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["telegram_id"] == 999111333

    # Noto'g'ri initData
    res_invalid = await async_client.post(
        "/api/v1/auth/telegram-webapp",
        json={"init_data": "invalid_init_data_here"},
    )
    assert res_invalid.status_code == 401
