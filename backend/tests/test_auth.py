import hashlib
import hmac
import json
import time
import pytest
from app.core.security import create_access_token, decode_access_token, validate_telegram_init_data


def generate_valid_tg_init_data(bot_token: str, user_dict: dict, auth_date: int = None) -> str:
    """Haqiqiy Telegram Mini App initData satrini va hashini yasash helperi"""
    if auth_date is None:
        auth_date = int(time.time())

    params = {
        "auth_date": str(auth_date),
        "query_id": "AAHdF6IQAAAAAN0XohD7VqQe",
        "user": json.dumps(user_dict, separators=(",", ":")),
    }

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    params["hash"] = calc_hash
    return "&".join(f"{k}={v}" for k, v in params.items())


def test_telegram_init_data_validation_success():
    bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
    user_info = {
        "id": 555666777,
        "first_name": "Sardor",
        "last_name": "Karimov",
        "username": "sardor_k",
        "language_code": "uz",
    }
    init_data = generate_valid_tg_init_data(bot_token, user_info)
    
    result = validate_telegram_init_data(init_data, bot_token=bot_token)
    assert result is not None
    assert "user" in result
    assert result["user"]["id"] == 555666777
    assert result["user"]["first_name"] == "Sardor"


def test_telegram_init_data_invalid_hash():
    bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz1234567"
    user_info = {"id": 111, "first_name": "Hacker"}
    init_data = generate_valid_tg_init_data(bot_token, user_info)
    
    # Hashni qasddan buzish
    tampered_data = init_data.replace("hash=", "hash=invalidhashvalue")
    result = validate_telegram_init_data(tampered_data, bot_token=bot_token)
    assert result is None


def test_jwt_token_flow():
    payload_data = {"user_id": 42, "role": "USER", "sub": "999"}
    token = create_access_token(payload_data, expires_delta_seconds=3600)
    assert isinstance(token, str)

    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["user_id"] == 42
    assert decoded["role"] == "USER"
    assert decoded["sub"] == "999"


def test_jwt_invalid_token():
    decoded = decode_access_token("completely-invalid-token")
    assert decoded is None
