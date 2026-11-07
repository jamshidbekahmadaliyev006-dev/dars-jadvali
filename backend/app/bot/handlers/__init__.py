from app.bot.handlers.start import router as start_router
from app.bot.handlers.admin_menu import router as admin_router
from app.bot.handlers.user_menu import router as user_router

__all__ = ["start_router", "admin_router", "user_router"]
