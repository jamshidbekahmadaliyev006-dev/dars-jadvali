import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api_router import api_router
from app.bot.bot_instance import get_bot
from app.bot.dispatcher import setup_dispatcher
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.logging import logger, setup_logging
from app.scheduler.setup import start_scheduler, stop_scheduler

# Log tizimini ishga tushirish
setup_logging()

bot_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bot_task
    logger.info("UniNotify platform starting up...")

    # 1. Ma'lumotlar bazasini initsializatsiya qilish
    await init_db()

    # 2. Background schedulerni ishga tushirish
    await start_scheduler()

    # 3. Telegram Botni ishga tushirish (agar token to'g'ri sozlangan bo'lsa)
    bot = get_bot()
    if bot:
        dp = setup_dispatcher()
        logger.info("Starting Telegram Bot polling in background...")
        # Pollingni alohida asyncio task sifatida boshlash
        bot_task = asyncio.create_task(dp.start_polling(bot, handle_signals=False))
    else:
        logger.info("Telegram Bot polling skipped (Token is placeholder or not provided).")

    yield

    logger.info("UniNotify platform shutting down...")
    # 1. Botni to'xtatish
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

    bot = get_bot()
    if bot:
        await bot.session.close()

    # 2. Schedulerni to'xtatish
    await stop_scheduler()

    # 3. Ma'lumotlar bazasini yopish
    await close_db()
    logger.info("UniNotify platform stopped cleanly.")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Universal University Student Platform — API & Telegram Bot Backend",
        lifespan=lifespan,
    )

    # CORS sozlamalari (Mini App brauzer ichidan ulanishi uchun)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routerlarni ulash
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"])
    async def root():
        return {
            "name": settings.PROJECT_NAME,
            "version": "0.1.0",
            "status": "running",
            "docs_url": "/docs",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
