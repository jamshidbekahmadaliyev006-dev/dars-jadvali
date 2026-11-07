import os
import sys
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# backend yo'lini sys.path ga qo'shish
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.base import Base
from app.models.enums import UserRole
from app.models.user import User

# Test database engine (StaticPool orqali bir xil in-memory sqlite ulanishini saqlaydi)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Har bir testdan oldin jadvallarni toza in-memory bazada yaratish"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Alohida test uchun async database session"""
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncClient:
    """FastAPI test HTTP client"""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_student_user(db_session: AsyncSession) -> User:
    """Oddiy talaba foydalanuvchisi fixture"""
    student = User(
        telegram_id=111222333,
        first_name="Ali",
        last_name="Valiyev",
        username="ali_valiyev",
        role=UserRole.USER,
        language_code="uz",
        is_active=True,
    )
    db_session.add(student)
    await db_session.commit()
    await db_session.refresh(student)
    return student


@pytest_asyncio.fixture
async def test_admin_user(db_session: AsyncSession) -> User:
    """Administrator foydalanuvchisi fixture"""
    admin = User(
        telegram_id=999888777,
        first_name="Admin",
        last_name="Super",
        username="uninotify_admin",
        role=UserRole.ADMIN,
        language_code="uz",
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
def student_auth_headers(test_student_user: User) -> dict:
    """Talaba uchun JWT Header"""
    token = create_access_token({
        "sub": str(test_student_user.telegram_id),
        "user_id": test_student_user.id,
        "role": test_student_user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_auth_headers(test_admin_user: User) -> dict:
    """Admin uchun JWT Header"""
    token = create_access_token({
        "sub": str(test_admin_user.telegram_id),
        "user_id": test_admin_user.id,
        "role": test_admin_user.role.value,
    })
    return {"Authorization": f"Bearer {token}"}
