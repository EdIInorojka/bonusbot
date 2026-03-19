import json
import re
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.bot.services.content import (
    ALLOWED_ACTIONS,
    REQUIRED_STEP_SLUGS,
    DynamicButton,
    DynamicFunnelStep,
    get_funnel_steps,
    get_links_config,
    save_funnel_steps,
    save_links_config,
)
from app.db.models.media_asset import MediaAsset


router = APIRouter(prefix="/admin/content", tags=["admin-content"])

FIXED_LINK_KEYS = [
    "channel",
    "registration",
    "deposit",
    "instruction",
    "instruction_message",
    "bonus",
    "signal",
    "webapp",
]


def _sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _buttons_to_json(step: DynamicFunnelStep) -> str:
    payload = [{"text": b.text, "action": b.action, "value": b.value} for b in step.buttons]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _parse_buttons_json(buttons_json: str) -> tuple[DynamicButton, ...]:
    try:
        raw = json.loads(buttons_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Невалидный JSON кнопок: {exc}") from exc

    if not isinstance(raw, list):
        raise ValueError("Кнопки должны быть массивом JSON")

    buttons: list[DynamicButton] = []
    for idx, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Кнопка #{idx}: должен быть объект")
        text = str(item.get("text", "")).strip()
        action = str(item.get("action", "")).strip()
        value = str(item.get("value", "")).strip()
        if not text:
            raise ValueError(f"Кнопка #{idx}: пустой text")
        if action not in ALLOWED_ACTIONS:
            raise ValueError(f"Кнопка #{idx}: action должен быть одним из {sorted(ALLOWED_ACTIONS)}")
        buttons.append(DynamicButton(text=text, action=action, value=value))

    return tuple(buttons)


def _parse_buttons_from_form(form) -> tuple[DynamicButton, ...]:
    texts = form.getlist("btn_text")
    actions = form.getlist("btn_action")
    values = form.getlist("btn_value")

    if texts or actions or values:
        max_len = max(len(texts), len(actions), len(values))
        buttons: list[DynamicButton] = []
        for i in range(max_len):
            text = texts[i].strip() if i < len(texts) else ""
            action = actions[i].strip() if i < len(actions) else ""
            value = values[i].strip() if i < len(values) else ""

            if not text and not action and not value:
                continue
            if not text:
                raise ValueError(f"Кнопка #{i + 1}: пустой text")
            if action not in ALLOWED_ACTIONS:
                raise ValueError(f"Кнопка #{i + 1}: action должен быть одним из {sorted(ALLOWED_ACTIONS)}")
            buttons.append(DynamicButton(text=text, action=action, value=value))
        return tuple(buttons)

    return _parse_buttons_json(str(form.get("buttons_json", "[]")))


@router.get("")
async def content_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    links = await get_links_config(session)
    steps = await get_funnel_steps(session)
    assets = (
        await session.execute(select(MediaAsset).order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc()))
    ).scalars().all()

    extra_links = {k: v for k, v in links.items() if k not in FIXED_LINK_KEYS}
    steps_view = [
        {
            "step": step,
            "buttons_json": _buttons_to_json(step),
            "buttons": [{"text": b.text, "action": b.action, "value": b.value} for b in step.buttons],
            "is_required": step.slug in REQUIRED_STEP_SLUGS,
        }
        for step in steps
    ]

    return templates.TemplateResponse(
        request,
        "content.html",
        {
            "request": request,
            "links": links,
            "extra_links_json": json.dumps(extra_links, ensure_ascii=False, indent=2),
            "steps_view": steps_view,
            "step_targets": [{"step": s.step, "title": s.title} for s in steps],
            "media_assets": assets,
            "required_step_slugs": list(REQUIRED_STEP_SLUGS),
            "allowed_actions": sorted(ALLOWED_ACTIONS),
            "msg": request.query_params.get("msg", ""),
            "error": request.query_params.get("error", ""),
            "next_step_default": (steps[-1].step + 1) if steps else 1,
        },
    )


@router.post("/links")
async def update_links(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    channel: str = Form(""),
    registration: str = Form(""),
    deposit: str = Form(""),
    instruction: str = Form(""),
    instruction_message: str = Form(""),
    bonus: str = Form(""),
    signal: str = Form(""),
    webapp: str = Form(""),
    extra_links_json: str = Form("{}"),
):
    links = {
        "channel": channel.strip(),
        "registration": registration.strip(),
        "deposit": deposit.strip(),
        "instruction": instruction.strip(),
        "instruction_message": instruction_message.strip(),
        "bonus": bonus.strip(),
        "signal": signal.strip(),
        "webapp": webapp.strip(),
    }

    if extra_links_json.strip():
        try:
            extra = json.loads(extra_links_json)
        except json.JSONDecodeError as exc:
            return RedirectResponse(
                url=f"/admin/content?error={quote_plus(f'Ошибка JSON ссылок: {exc}')}",
                status_code=302,
            )

        if not isinstance(extra, dict):
            return RedirectResponse(
                url=f"/admin/content?error={quote_plus('extra_links_json должен быть объектом')}",
                status_code=302,
            )

        for key, value in extra.items():
            k = str(key).strip()
            if not k:
                continue
            links[k] = str(value).strip()

    await save_links_config(session, links)
    await session.commit()
    return RedirectResponse(url="/admin/content?msg=Ссылки+сохранены", status_code=302)


@router.post("/steps/save")
async def save_step(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    form = await request.form()
    try:
        original_step_raw = str(form.get("original_step", "")).strip()
        original_step = int(original_step_raw) if original_step_raw else None

        step = int(str(form.get("step", "")).strip())
        if step < 1:
            raise ValueError("step должен быть >= 1")

        title = str(form.get("title", "")).strip()
        if not title:
            raise ValueError("title не может быть пустым")

        slug = _sanitize_slug(str(form.get("slug", "")).strip())
        if not slug:
            raise ValueError("slug не может быть пустым")

        text = str(form.get("text", "")).strip()
        if not text:
            raise ValueError("text не может быть пустым")

        photo = str(form.get("photo", "")).strip()
        buttons = _parse_buttons_from_form(form)

        steps = await get_funnel_steps(session)
        original_item = next((s for s in steps if s.step == original_step), None) if original_step else None

        if original_item and original_item.slug in REQUIRED_STEP_SLUGS and slug != original_item.slug:
            raise ValueError("Slug обязательного шага менять нельзя")

        duplicate_slug = next((s for s in steps if s.slug == slug and s.step != (original_step or step)), None)
        if duplicate_slug:
            raise ValueError("Slug уже занят другим шагом")

        new_step = DynamicFunnelStep(
            step=step,
            title=title,
            slug=slug,
            text=text,
            photo=photo,
            buttons=buttons,
        )

        next_steps = [s for s in steps if s.step != step]
        if original_step is not None and original_step != step:
            next_steps = [s for s in next_steps if s.step != original_step]

        next_steps.append(new_step)
        await save_funnel_steps(session, next_steps)
        await session.commit()
    except ValueError as exc:
        return RedirectResponse(
            url=f"/admin/content?error={quote_plus(str(exc))}",
            status_code=302,
        )

    return RedirectResponse(url="/admin/content?msg=Шаг+сохранен", status_code=302)


@router.post("/steps/{step_id}/delete")
async def delete_step(
    step_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    steps = await get_funnel_steps(session)
    target = next((s for s in steps if s.step == step_id), None)

    if target and target.slug in REQUIRED_STEP_SLUGS:
        return RedirectResponse(
            url="/admin/content?error=Нельзя+удалить+обязательный+шаг",
            status_code=302,
        )

    next_steps = [s for s in steps if s.step != step_id]

    if not next_steps:
        return RedirectResponse(
            url="/admin/content?error=Нельзя+удалить+последний+шаг",
            status_code=302,
        )

    await save_funnel_steps(session, next_steps)
    await session.commit()
    return RedirectResponse(url="/admin/content?msg=Шаг+удален", status_code=302)