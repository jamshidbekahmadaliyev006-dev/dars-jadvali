"""
Admin saytga kirish (oddiy brauzerda).

Admin botdagi "Admin sayt" tugmasini bosadi. Bot unga BIR MARTALIK havola beradi (5 daqiqa amal qiladi).
Sayt shu havolani sessiya tokeniga almashtiradi (24 soat). Ikkalasi ham bot tokenidan olingan sir bilan
imzolanadi, shuning uchun ularni boshqa hech kim yarata olmaydi. Har so'rovda admin hali ADMIN_IDS'da
ekani qayta tekshiriladi: ro'yxatdan chiqarilgan odamning sessiyasi darhol to'xtaydi.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Dict, Optional

from app.core.config import settings

LOGIN_TTL_SECONDS = 5 * 60
SESSION_TTL_SECONDS = 24 * 60 * 60

# Ishlatilgan havolalar (jti -> tugash vaqti). Server qayta ishga tushsa tozalanadi, havola esa baribir 5 daqiqada eskiradi.
_USED_LOGINS: Dict[str, float] = {}


def _key() -> bytes:
    # Bot tokeni repoda yo'q, shuning uchun SECRET_KEY standart bo'lib qolsa ham imzoni soxtalab bo'lmaydi
    return hashlib.sha256(f"{settings.BOT_TOKEN}|{settings.SECRET_KEY}|qulay-jadval-admin".encode()).digest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: dict) -> str:
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    signature = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _open(token: str, kind: str, now: float) -> Optional[dict]:
    """Imzo, tur (login/session) va muddatni tekshiradi; noto'g'ri bo'lsa None"""
    try:
        body, signature = (token or "").split(".")
        expected = _b64(hmac.new(_key(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(expected, signature):
            return None
        data = json.loads(_unb64(body))
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("k") != kind or not isinstance(data.get("id"), int):
        return None
    if float(data.get("exp", 0)) < now:
        return None
    return data


def create_login_token(telegram_id: int, now: Optional[float] = None) -> str:
    now = now or time.time()
    return _sign({"k": "login", "id": telegram_id, "exp": now + LOGIN_TTL_SECONDS, "jti": secrets.token_urlsafe(9)})


def create_session_token(telegram_id: int, now: Optional[float] = None) -> str:
    now = now or time.time()
    return _sign({"k": "session", "id": telegram_id, "exp": now + SESSION_TTL_SECONDS})


def exchange_login_token(token: str, now: Optional[float] = None) -> Optional[int]:
    """Bir martalik havolani ishlatadi: to'g'ri bo'lsa admin Telegram ID'sini qaytaradi va havola yonadi"""
    now = now or time.time()
    data = _open(token, "login", now)
    if not data:
        return None
    for jti, exp in list(_USED_LOGINS.items()):
        if exp < now:
            del _USED_LOGINS[jti]
    jti = str(data.get("jti") or "")
    if not jti or jti in _USED_LOGINS:
        return None
    _USED_LOGINS[jti] = float(data["exp"])
    return data["id"]


def verify_session(token: str, now: Optional[float] = None) -> Optional[int]:
    data = _open(token, "session", now or time.time())
    return data["id"] if data else None
