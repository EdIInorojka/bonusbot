from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user_conversion import UserConversion


REGISTRATION_EVENT_KEYWORDS = ("registration", "register", "signup", "sign_up", "reg")
FIRST_DEPOSIT_EVENT_KEYWORDS = ("first_deposit", "first-deposit", "ftd", "deposit")


def is_registration_event(event_name: str) -> bool:
    normalized = (event_name or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in REGISTRATION_EVENT_KEYWORDS)


def is_first_deposit_event(event_name: str) -> bool:
    normalized = (event_name or "").strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in FIRST_DEPOSIT_EVENT_KEYWORDS)


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
        "sub1",
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


def extract_amount(payload: dict[str, Any]) -> float | None:
    candidates = ("amount", "sum", "value", "deposit", "first_deposit_amount")
    for key in candidates:
        value = payload.get(key)
        if value is None:
            continue
        raw = str(value).strip().replace(",", ".")
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


async def is_user_registered(session: AsyncSession, user_id: int) -> bool:
    row = await session.get(UserConversion, user_id)
    return bool(row and row.is_registered)


async def _get_or_create_conversion(session: AsyncSession, user_id: int) -> UserConversion:
    row = await session.get(UserConversion, user_id)
    if not row:
        row = UserConversion(user_id=user_id)
        session.add(row)
    return row


async def mark_user_registered(
    session: AsyncSession,
    user_id: int,
    event_name: str,
    payload: dict[str, Any],
) -> UserConversion:
    row = await _get_or_create_conversion(session, user_id)
    now = datetime.now(timezone.utc)

    row.is_registered = True
    row.registration_confirmed_at = now
    row.last_event_name = event_name[:128] if event_name else "registration"
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.event_count = int(row.event_count or 0) + 1
    row.last_seen_at = now

    await session.flush()
    return row


async def mark_first_deposit(
    session: AsyncSession,
    user_id: int,
    event_name: str,
    payload: dict[str, Any],
) -> UserConversion:
    row = await _get_or_create_conversion(session, user_id)
    now = datetime.now(timezone.utc)

    row.has_first_deposit = True
    row.first_deposit_confirmed_at = now
    amount = extract_amount(payload)
    if amount is not None:
        row.first_deposit_amount = amount

    row.last_event_name = event_name[:128] if event_name else "first_deposit"
    row.payload_json = json.dumps(payload, ensure_ascii=False)
    row.event_count = int(row.event_count or 0) + 1
    row.last_seen_at = now

    await session.flush()
    return row
