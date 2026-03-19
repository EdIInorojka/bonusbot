from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.content_defaults import DEFAULT_FUNNEL_STEPS, DEFAULT_LINKS
from app.core.config import build_webapp_url, get_settings
from app.db.models.admin_settings import AdminSettings


LINKS_SETTING_KEY = "links_json"
FUNNEL_SETTING_KEY = "funnel_steps_json"
ALLOWED_ACTIONS = {"url", "webapp", "callback", "next", "share"}


@dataclass(frozen=True)
class DynamicButton:
    text: str
    action: str
    value: str


@dataclass(frozen=True)
class DynamicFunnelStep:
    step: int
    text: str
    photo: str
    buttons: tuple[DynamicButton, ...]



def _dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)



def _load_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return fallback



def _default_links_from_settings() -> dict[str, str]:
    settings = get_settings()
    default_links = dict(DEFAULT_LINKS)
    default_links.update(
        {
            "channel": settings.channel_url,
            "registration": settings.registration_url,
            "deposit": settings.deposit_url,
            "instruction": settings.instruction_url,
            "instruction_message": settings.instruction_message,
            "bonus": settings.bonus_claim_url,
            "signal": settings.signal_url,
            "webapp": build_webapp_url(),
        }
    )
    return default_links


async def _get_setting_row(session: AsyncSession, key: str) -> AdminSettings | None:
    return await session.get(AdminSettings, key)


async def _get_or_create_json_setting(session: AsyncSession, key: str, default_value: Any) -> Any:
    row = await _get_setting_row(session, key)
    if not row:
        session.add(AdminSettings(key=key, value=_dump_json(default_value)))
        await session.flush()
        return default_value
    return _load_json(row.value, default_value)


async def _set_json_setting(session: AsyncSession, key: str, value: Any) -> None:
    row = await _get_setting_row(session, key)
    encoded = _dump_json(value)
    if not row:
        session.add(AdminSettings(key=key, value=encoded))
        await session.flush()
        return
    row.value = encoded
    await session.flush()



def _normalize_button(raw: Any) -> DynamicButton | None:
    if not isinstance(raw, dict):
        return None

    text = str(raw.get("text", "")).strip()
    action = str(raw.get("action", "")).strip()
    value = str(raw.get("value", "")).strip()
    if not text or action not in ALLOWED_ACTIONS:
        return None
    if action == "callback" and value == "lang":
        return None
    return DynamicButton(text=text, action=action, value=value)



def _normalize_step(raw: Any) -> DynamicFunnelStep | None:
    if not isinstance(raw, dict):
        return None

    try:
        step_id = int(raw.get("step"))
    except Exception:
        return None

    if step_id < 1:
        return None

    text = str(raw.get("text", "")).strip()
    if not text:
        return None

    photo = str(raw.get("photo", "")).strip()
    raw_buttons = raw.get("buttons", [])
    buttons: list[DynamicButton] = []

    if isinstance(raw_buttons, list):
        for item in raw_buttons:
            button = _normalize_button(item)
            if button:
                buttons.append(button)

    return DynamicFunnelStep(step=step_id, text=text, photo=photo, buttons=tuple(buttons))



def step_to_storage(step: DynamicFunnelStep) -> dict[str, Any]:
    return {
        "step": step.step,
        "text": step.text,
        "photo": step.photo,
        "buttons": [
            {"text": btn.text, "action": btn.action, "value": btn.value}
            for btn in step.buttons
        ],
    }


async def get_links_config(session: AsyncSession) -> dict[str, str]:
    defaults = _default_links_from_settings()
    raw = await _get_or_create_json_setting(session, LINKS_SETTING_KEY, defaults)

    links = dict(defaults)
    if isinstance(raw, dict):
        for key, value in raw.items():
            k = str(key).strip()
            if not k:
                continue
            links[k] = str(value).strip()

    if not links.get("webapp"):
        links["webapp"] = build_webapp_url()

    return links


async def save_links_config(session: AsyncSession, links: dict[str, str]) -> None:
    normalized: dict[str, str] = {}
    for key, value in links.items():
        k = str(key).strip()
        if not k:
            continue
        normalized[k] = str(value).strip()

    if "webapp" not in normalized or not normalized.get("webapp"):
        normalized["webapp"] = build_webapp_url()

    await _set_json_setting(session, LINKS_SETTING_KEY, normalized)


async def get_funnel_steps(session: AsyncSession) -> list[DynamicFunnelStep]:
    raw = await _get_or_create_json_setting(session, FUNNEL_SETTING_KEY, DEFAULT_FUNNEL_STEPS)

    steps: list[DynamicFunnelStep] = []
    if isinstance(raw, list):
        for item in raw:
            step = _normalize_step(item)
            if step:
                steps.append(step)

    if not steps:
        for item in DEFAULT_FUNNEL_STEPS:
            step = _normalize_step(item)
            if step:
                steps.append(step)

    unique: dict[int, DynamicFunnelStep] = {step.step: step for step in steps}
    ordered = sorted(unique.values(), key=lambda x: x.step)
    return ordered


async def save_funnel_steps(session: AsyncSession, steps: list[DynamicFunnelStep]) -> None:
    ordered = sorted(steps, key=lambda x: x.step)
    payload = [step_to_storage(step) for step in ordered]
    await _set_json_setting(session, FUNNEL_SETTING_KEY, payload)


async def upsert_funnel_step(session: AsyncSession, new_step: DynamicFunnelStep) -> list[DynamicFunnelStep]:
    steps = await get_funnel_steps(session)
    items = [step for step in steps if step.step != new_step.step]
    items.append(new_step)
    await save_funnel_steps(session, items)
    return sorted(items, key=lambda x: x.step)


async def delete_funnel_step(session: AsyncSession, step_id: int) -> list[DynamicFunnelStep]:
    steps = await get_funnel_steps(session)
    items = [step for step in steps if step.step != step_id]
    if not items:
        default_first = _normalize_step(DEFAULT_FUNNEL_STEPS[0])
        if default_first:
            items = [default_first]
    await save_funnel_steps(session, items)
    return sorted(items, key=lambda x: x.step)



def get_step_by_id(steps: list[DynamicFunnelStep], step_id: int) -> DynamicFunnelStep:
    if not steps:
        fallback = _normalize_step(DEFAULT_FUNNEL_STEPS[0])
        if not fallback:
            raise RuntimeError("No funnel steps configured")
        return fallback

    by_id = {step.step: step for step in steps}
    if step_id in by_id:
        return by_id[step_id]

    ordered_ids = [step.step for step in steps]
    if step_id < ordered_ids[0]:
        return by_id[ordered_ids[0]]
    return by_id[ordered_ids[-1]]



def step_ids(steps: list[DynamicFunnelStep]) -> list[int]:
    return [step.step for step in steps]



def next_step_id(current_step: int, steps: list[DynamicFunnelStep]) -> int:
    ids = step_ids(steps)
    if not ids:
        return 1

    for step_id in ids:
        if step_id > current_step:
            return step_id
    return ids[-1]



def prev_step_id(current_step: int, steps: list[DynamicFunnelStep]) -> int:
    ids = step_ids(steps)
    if not ids:
        return 1

    prev = ids[0]
    for step_id in ids:
        if step_id >= current_step:
            return prev
        prev = step_id
    return ids[-1]



def step_position(step: DynamicFunnelStep, steps: list[DynamicFunnelStep]) -> tuple[int, int]:
    ordered = step_ids(steps)
    if not ordered:
        return (1, 1)
    try:
        pos = ordered.index(step.step) + 1
    except ValueError:
        pos = len(ordered)
    return (pos, len(ordered))
