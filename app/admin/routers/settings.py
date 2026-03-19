from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.core.config import get_settings
from app.db.models.admin_settings import AdminSettings


router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


DEFAULT_KEYS = {
    "global_win_rate": lambda: str(get_settings().global_win_rate),
    "spin_cooldown_seconds": lambda: str(get_settings().spin_cooldown_seconds),
    "max_daily_spins_per_user": lambda: str(get_settings().max_daily_spins_per_user),
}


async def _get_value(session: AsyncSession, key: str) -> str:
    row = await session.get(AdminSettings, key)
    if row:
        return row.value
    return DEFAULT_KEYS[key]()


async def _set_value(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AdminSettings, key)
    if row:
        row.value = value
    else:
        session.add(AdminSettings(key=key, value=value))


@router.get("")
async def settings_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    data = {}
    for key in DEFAULT_KEYS:
        data[key] = await _get_value(session, key)

    return templates.TemplateResponse(
        request,
        "settings.html",
        {"request": request, "data": data},
    )


@router.post("")
async def settings_update(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    global_win_rate: float = Form(...),
    spin_cooldown_seconds: int = Form(...),
    max_daily_spins_per_user: int = Form(...),
):
    await _set_value(session, "global_win_rate", str(max(0.0, min(global_win_rate, 1.0))))
    await _set_value(session, "spin_cooldown_seconds", str(max(30, spin_cooldown_seconds)))
    await _set_value(session, "max_daily_spins_per_user", str(max(1, max_daily_spins_per_user)))
    await session.commit()
    return RedirectResponse(url="/admin/settings", status_code=302)
