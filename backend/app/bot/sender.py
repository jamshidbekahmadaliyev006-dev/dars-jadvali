"""Xabarni ishonchli yuborish: Telegram tezlik chegarasi va vaqtinchalik xatolarda qayta uriniladi."""
import asyncio
from typing import Tuple
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter

OK, BLOCKED, NOT_STARTED, FAILED = "ok", "blocked", "not_started", "failed"


async def safe_send(bot, chat_id: int, text: str, attempts: int = 4, **kwargs) -> Tuple[str, str]:
    """(holat, izoh). Holat: ok / blocked (botni bloklagan) / not_started (/start bosmagan) / failed"""
    last = ""
    for attempt in range(attempts):
        try:
            await bot.send_message(chat_id=chat_id, text=text, **kwargs)
            return OK, ""
        except TelegramRetryAfter as e:
            await asyncio.sleep(min(float(e.retry_after) + 0.5, 30))
            last = "rate limit"
        except TelegramForbiddenError as e:
            msg = str(e).lower()
            return (NOT_STARTED if "initiate" in msg else BLOCKED), str(e)[:80]
        except TelegramBadRequest as e:
            msg = str(e).lower()
            if "chat not found" in msg or "user not found" in msg:
                return NOT_STARTED, str(e)[:80]
            return FAILED, str(e)[:80]
        except (TelegramNetworkError, asyncio.TimeoutError) as e:
            await asyncio.sleep(1 + attempt)
            last = type(e).__name__
        except Exception as e:
            return FAILED, type(e).__name__
    return FAILED, last
