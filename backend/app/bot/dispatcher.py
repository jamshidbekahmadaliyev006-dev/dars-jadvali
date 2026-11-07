from aiogram import Dispatcher
from app.bot.handlers.admin_menu import router as admin_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.user_menu import router as user_router
from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.db_session import DbSessionMiddleware
from app.core.logging import logger


def setup_dispatcher() -> Dispatcher:
    """Aiogram Dispatcher'ni sozlash va barcha middleware hamda routerlarni ulash"""
    dp = Dispatcher()

    # Middlewares (tartib muhim: avval db session, keyin auth)
    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers (start, admin, user)
    dp.include_router(start_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    logger.info("Bot Dispatcher configured with middlewares and routers.")
    return dp
