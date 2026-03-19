import hashlib
import hmac
import json
from urllib.parse import parse_qsl


def verify_telegram_init_data(init_data: str, bot_token: str) -> dict:
    if not init_data:
        raise ValueError("Missing Telegram init data")

    data = dict(parse_qsl(init_data, strict_parsing=True))
    recv_hash = data.pop("hash", None)
    if not recv_hash:
        raise ValueError("Missing hash in init data")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc_hash = hmac.new(secret_key, data_check.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calc_hash, recv_hash):
        raise ValueError("Invalid Telegram init data hash")

    user_raw = data.get("user")
    user = json.loads(user_raw) if user_raw else {}
    return {"raw": data, "user": user}
