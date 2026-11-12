from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.bot.handlers.admin_menu import router as admin_router
from app.bot.handlers.contact import router as contact_router
from app.bot.handlers.plans import router as plans_router
from app.bot.handlers.registration import router as registration_router
from app.bot.handlers.start import router as start_router
from app.bot.handlers.teacher import router as teacher_router
from app.bot.handlers.user_menu import router as user_router
from app.bot.middlewares.auth import AuthMiddleware
from app.bot.middlewares.db_session import DbSessionMiddleware
from app.bot.middlewares.menu_reset import MenuResetMiddleware
from app.core.logging import logger


def setup_dispatcher() -> Dispatcher:
    """Aiogram Dispatcher'ni sozlash va barcha middleware hamda routerlarni ulash"""
    dp = Dispatcher(storage=MemoryStorage())

    # Middlewares (tartib muhim: avval db session, keyin auth)
    dp.message.middleware(DbSessionMiddleware())
    dp.message.middleware(AuthMiddleware())
    dp.message.outer_middleware(MenuResetMiddleware())  # handler tanlanishidan OLDIN ishlashi shart
    dp.callback_query.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # Routers (start, registration-FSM, admin, user - registration FSM state handlers
    # bosqichida bo'lsa, oddiy menyu matn handlerlaridan oldin ishlashi kerak)
    dp.include_router(start_router)
    dp.include_router(registration_router)
    dp.include_router(contact_router)
    dp.include_router(plans_router)
    dp.include_router(teacher_router)
    dp.include_router(admin_router)
    dp.include_router(user_router)

    logger.info("Bot Dispatcher configured with middlewares and routers.")
    return dp
