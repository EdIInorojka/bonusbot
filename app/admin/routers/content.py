import json
import re
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
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

PREFERRED_LINK_ORDER = [
    "channel",
    "registration",
    "deposit",
    "instruction",
    "bonus",
    "signal",
    "webapp",
    "mines_webapp",
]


def _sanitize_slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def _sanitize_link_key(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower())
    return cleaned.strip("_")


def _buttons_to_json(step: DynamicFunnelStep) -> str:
    payload = [{"text": b.text, "action": b.action, "value": b.value} for b in step.buttons]
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _is_ajax(request: Request) -> bool:
    return request.headers.get("x-requested-with", "").lower() == "xmlhttprequest"


def _response_ok(request: Request, message: str) -> JSONResponse | RedirectResponse:
    if _is_ajax(request):
        return JSONResponse({"ok": True, "message": message})
    return RedirectResponse(url=f"/admin/content?msg={quote_plus(message)}", status_code=302)


def _response_error(request: Request, message: str, status_code: int = 400) -> JSONResponse | RedirectResponse:
    if _is_ajax(request):
        return JSONResponse({"ok": False, "message": message}, status_code=status_code)
    return RedirectResponse(url=f"/admin/content?error={quote_plus(message)}", status_code=302)


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
        if not value:
            raise ValueError(f"Кнопка #{idx}: value обязателен")

        buttons.append(DynamicButton(text=text, action=action, value=value))

    if not buttons:
        raise ValueError("У шага должна быть хотя бы одна кнопка")

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

            if not text:
                raise ValueError(f"Кнопка #{i + 1}: пустой text")
            if action not in ALLOWED_ACTIONS:
                raise ValueError(f"Кнопка #{i + 1}: action должен быть одним из {sorted(ALLOWED_ACTIONS)}")
            if not value:
                raise ValueError(f"Кнопка #{i + 1}: value обязателен")

            buttons.append(DynamicButton(text=text, action=action, value=value))

        if not buttons:
            raise ValueError("У шага должна быть хотя бы одна кнопка")

        return tuple(buttons)

    return _parse_buttons_json(str(form.get("buttons_json", "[]")))


def _validate_redirect_targets(
    buttons: tuple[DynamicButton, ...],
    available_step_ids: set[int],
) -> tuple[DynamicButton, ...]:
    validated: list[DynamicButton] = []

    for idx, btn in enumerate(buttons, start=1):
        if btn.action != "next":
            validated.append(btn)
            continue

        raw = (btn.value or "").strip()
        if not raw:
            raise ValueError(f"Кнопка #{idx}: для action=next выбери целевой шаг")
        try:
            target = int(raw)
        except ValueError as exc:
            raise ValueError(f"Кнопка #{idx}: target должен быть номером шага") from exc
        if target not in available_step_ids:
            raise ValueError(f"Кнопка #{idx}: target шага #{target} не найден")

        validated.append(DynamicButton(text=btn.text, action=btn.action, value=str(target)))

    return tuple(validated)


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

    instruction_message = links.get("instruction_message", "")
    links_without_instruction = {k: v for k, v in links.items() if k != "instruction_message"}
    ordered_keys = [
        *[key for key in PREFERRED_LINK_ORDER if key in links_without_instruction],
        *sorted(key for key in links_without_instruction if key not in PREFERRED_LINK_ORDER),
    ]

    link_items = [{"key": key, "value": links_without_instruction.get(key, "")} for key in ordered_keys]
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
            "instruction_message": instruction_message,
            "link_items": link_items,
            "link_keys": [item["key"] for item in link_items],
            "steps_view": steps_view,
            "step_targets": [{"step": s.step, "title": s.title, "slug": s.slug} for s in steps],
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
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    form = await request.form()
    instruction_message = str(form.get("instruction_message", "")).strip()
    keys = form.getlist("link_key")
    values = form.getlist("link_value")

    if not instruction_message:
        return _response_error(request, "instruction_message обязателен")

    if not keys and not values:
        return _response_error(request, "Добавь хотя бы одну ссылку")

    max_len = max(len(keys), len(values))
    links: dict[str, str] = {}

    for idx in range(max_len):
        raw_key = keys[idx] if idx < len(keys) else ""
        raw_value = values[idx] if idx < len(values) else ""

        key = _sanitize_link_key(str(raw_key))
        value = str(raw_value).strip()

        if not key:
            return _response_error(request, f"Ссылка #{idx + 1}: пустой ключ")
        if not value:
            return _response_error(request, f"Ссылка #{idx + 1}: пустое значение")
        if key in links:
            return _response_error(request, f"Дублирующийся ключ ссылки: {key}")

        links[key] = value

    links["instruction_message"] = instruction_message

    await save_links_config(session, links)
    await session.commit()
    return _response_ok(request, "Ссылки сохранены")


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
        if not photo:
            raise ValueError("photo обязателен")

        buttons = _parse_buttons_from_form(form)

        steps = await get_funnel_steps(session)
        original_item = next((s for s in steps if s.step == original_step), None) if original_step else None

        if original_item and original_item.slug in REQUIRED_STEP_SLUGS and slug != original_item.slug:
            raise ValueError("Slug обязательного шага менять нельзя")

        duplicate_slug = next((s for s in steps if s.slug == slug and s.step != (original_step or step)), None)
        if duplicate_slug:
            raise ValueError("Slug уже занят другим шагом")

        available_step_ids = {s.step for s in steps}
        available_step_ids.add(step)
        buttons = _validate_redirect_targets(buttons, available_step_ids)

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
        return _response_error(request, str(exc))

    return _response_ok(request, "Шаг сохранен")


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
            url=f"/admin/content?error={quote_plus('Нельзя удалить обязательный шаг')}",
            status_code=302,
        )

    next_steps = [s for s in steps if s.step != step_id]
    if not next_steps:
        return RedirectResponse(
            url=f"/admin/content?error={quote_plus('Нельзя удалить последний шаг')}",
            status_code=302,
        )

    await save_funnel_steps(session, next_steps)
    await session.commit()
    return RedirectResponse(url=f"/admin/content?msg={quote_plus('Шаг удален')}", status_code=302)

