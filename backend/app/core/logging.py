import logging
import sys
from app.core.config import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"


def setup_logging():
    log_level = logging.DEBUG if settings.DEBUG else logging.INFO

    logging.basicConfig(
        level=log_level,
        format=LOG_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Shovqinli kutubxonalar log darajasini pasaytirish
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.INFO)

    logger = logging.getLogger("uninotify")
    logger.info(f"Logging initialized with level: {logging.getLevelName(log_level)}")
    return logger


logger = logging.getLogger("uninotify")
