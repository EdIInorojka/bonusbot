from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_conversion import UserConversion


REGISTRATION_EVENT_KEYWORDS = ("registration", "register", "signup", "sign_up", "reg")


def is_registration_event(event_name: str) -> bool:
    normalized = (event_name or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in REGISTRATION_EVENT_KEYWORDS)


def extract_event_name(payload: dict[str, Any]) -> str:
    candidates = (
        "event",
        "event_name",
        "event_type",
        "hash_name",
        "action",
        "status",
    )
    for key in candidates:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def extract_source_user_id(payload: dict[str, Any]) -> int | None:
    candidates = (
        "source_id",
        "sub_id",
        "subid",
        "tg_id",
        "telegram_id",
        "user_id",
        "userid",
        "uid",
    )
    for key in candidates:
        value = payload.get(key)
        if value is None:
            continue
        raw = str(value).strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None


async def is_user_registered(session: AsyncSession, user_id: int) -> bool:
    row = await session.get(UserConversion, user_id)
    return bool(row and row.is_registered)


async def mark_user_registered(
    session: AsyncSession,
    user_id: int,
    event_name: str,
    payload: dict[str, Any],
) -> UserConversion:
    row = await session.get(UserConversion, user_id)
    if not row:
        row = UserConversion(user_id=user_id)
        session.add(row)

    row.is_registered = True
    row.registration_confirmed_at = datetime.now(timezone.utc)
    row.last_event_name = event_name[:128] if event_name else "registration"
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.event_count = int(row.event_count or 0) + 1
    row.last_seen_at = datetime.now(timezone.utc)

    await session.flush()
    return row
