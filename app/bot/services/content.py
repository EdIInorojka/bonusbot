from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.content_defaults import DEFAULT_FUNNEL_STEPS, DEFAULT_LINKS
from app.core.config import build_webapp_url, get_settings
from app.db.models.admin_settings import AdminSettings


LINKS_SETTING_KEY = "links_json"
FUNNEL_SETTING_KEY = "funnel_steps_json"
ALLOWED_ACTIONS = {"url", "webapp", "callback", "next", "share"}
REQUIRED_STEP_SLUGS = ("primary_registration", "main_menu")


@dataclass(frozen=True)
class DynamicButton:
    text: str
    action: str
    value: str


@dataclass(frozen=True)
class DynamicFunnelStep:
    step: int
    title: str
    slug: str
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


def _sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _fallback_title(step_id: int) -> str:
    if step_id == 1:
        return "Primary Registration"
    if step_id == 2:
        return "Main Menu"
    return f"Step {step_id}"


def _fallback_slug(step_id: int) -> str:
    if step_id == 1:
        return "primary_registration"
    if step_id == 2:
        return "main_menu"
    return f"step_{step_id}"


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

    title = str(raw.get("title", "")).strip() or _fallback_title(step_id)
    raw_slug = str(raw.get("slug", "")).strip()
    slug = _sanitize_slug(raw_slug) if raw_slug else _fallback_slug(step_id)
    if not slug:
        slug = _fallback_slug(step_id)

    photo = str(raw.get("photo", "")).strip()
    raw_buttons = raw.get("buttons", [])
    buttons: list[DynamicButton] = []

    if isinstance(raw_buttons, list):
        for item in raw_buttons:
            button = _normalize_button(item)
            if button:
                buttons.append(button)

    return DynamicFunnelStep(
        step=step_id,
        title=title,
        slug=slug,
        text=text,
        photo=photo,
        buttons=tuple(buttons),
    )


def _with_step_id(step: DynamicFunnelStep, step_id: int) -> DynamicFunnelStep:
    return DynamicFunnelStep(
        step=step_id,
        title=step.title,
        slug=step.slug,
        text=step.text,
        photo=step.photo,
        buttons=step.buttons,
    )


def _ensure_required_steps(steps: list[DynamicFunnelStep]) -> list[DynamicFunnelStep]:
    defaults_by_slug: dict[str, DynamicFunnelStep] = {}
    for raw in DEFAULT_FUNNEL_STEPS:
        norm = _normalize_step(raw)
        if norm:
            defaults_by_slug[norm.slug] = norm

    by_slug = {step.slug: step for step in steps}
    used_ids = {step.step for step in steps}
    max_id = max(used_ids) if used_ids else 0

    fixed = list(steps)
    for slug in REQUIRED_STEP_SLUGS:
        if slug in by_slug:
            continue
        default = defaults_by_slug.get(slug)
        if not default:
            continue
        target_id = default.step
        if target_id in used_ids:
            max_id += 1
            target_id = max_id
        used_ids.add(target_id)
        fixed.append(_with_step_id(default, target_id))

    return fixed


def step_to_storage(step: DynamicFunnelStep) -> dict[str, Any]:
    return {
        "step": step.step,
        "title": step.title,
        "slug": step.slug,
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

    unique_by_id: dict[int, DynamicFunnelStep] = {step.step: step for step in steps}
    ordered = sorted(unique_by_id.values(), key=lambda x: x.step)

    unique_by_slug: dict[str, DynamicFunnelStep] = {}
    for step in ordered:
        if step.slug not in unique_by_slug:
            unique_by_slug[step.slug] = step
    ordered = sorted(unique_by_slug.values(), key=lambda x: x.step)

    ordered = _ensure_required_steps(ordered)
    ordered = sorted(ordered, key=lambda x: x.step)
    return ordered


async def save_funnel_steps(session: AsyncSession, steps: list[DynamicFunnelStep]) -> None:
    unique_by_id: dict[int, DynamicFunnelStep] = {step.step: step for step in steps}
    ordered = sorted(unique_by_id.values(), key=lambda x: x.step)
    ordered = _ensure_required_steps(ordered)
    ordered = sorted(ordered, key=lambda x: x.step)

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
    target = next((step for step in steps if step.step == step_id), None)
    if target and target.slug in REQUIRED_STEP_SLUGS:
        return steps

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


def get_step_by_slug(steps: list[DynamicFunnelStep], slug: str) -> DynamicFunnelStep | None:
    wanted = _sanitize_slug(slug)
    for step in steps:
        if step.slug == wanted:
            return step
    return None


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