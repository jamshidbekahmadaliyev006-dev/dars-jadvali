from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings
from app.core.logging import logger

# Async engine yaratish
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    # SQLite uchun connect_args
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

if "sqlite" in settings.DATABASE_URL:
    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        """Ko'p foydalanuvchi bir vaqtda yozganda qotib qolmasligi uchun: WAL + kutish vaqti"""
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=15000")
        cursor.close()


# Async session maker
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()


def _add_missing_columns(sync_conn) -> None:
    """create_all mavjud jadvalga yangi ustun qo'shmaydi: kerakli ustunlarni shu yerda qo'shamiz (bor bo'lsa tegmaydi)"""
    from sqlalchemy import inspect, text

    wanted = {
        "admin_broadcasts": [("kind", "VARCHAR(10) NOT NULL DEFAULT 'msg'")],
        "users": [("plan_only", "BOOLEAN NOT NULL DEFAULT 0")],
        "schedules": [("code", "VARCHAR(30)")],
        "teacher_lessons": [("code", "VARCHAR(30)")],
        "personal_events": [
            ("place", "VARCHAR(255)"), ("has_time", "BOOLEAN NOT NULL DEFAULT 1"),
            ("remind1_sent", "BOOLEAN NOT NULL DEFAULT 0"), ("remind2_sent", "BOOLEAN NOT NULL DEFAULT 0"),
        ],
    }
    insp = inspect(sync_conn)
    for table, columns in wanted.items():
        if not insp.has_table(table):
            continue
        have = {c["name"] for c in insp.get_columns(table)}
        for name, ddl in columns:
            if name not in have:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
                logger.info(f"Added column {table}.{name}")


async def init_db() -> None:
    """Initialize database tables"""
    from app.models.base import Base
    # Barcha modellarni import qilish orqali metadataga ro'yxatdan o'tkazish
    import app.models  # noqa: F401

    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_columns)
    logger.info("Database tables initialized successfully.")


async def close_db() -> None:
    """Close database connection engine"""
    logger.info("Closing database engine...")
    await engine.dispose()
    logger.info("Database engine closed.")
