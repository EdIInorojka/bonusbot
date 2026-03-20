
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.core.blob_storage import blob_is_enabled, delete_blob_object
from app.core.config import get_settings, is_ephemeral_database_url, mask_database_url
from app.db.models.admin_settings import AdminSettings
from app.db.models.bot_chat_state import BotChatState
from app.db.models.media_asset import MediaAsset, MediaAssetType
from app.db.models.referral import Referral
from app.db.models.spin import SpinHistory
from app.db.models.user import User
from app.db.models.user_conversion import UserConversion
from app.db.seed import seed as seed_defaults


router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])


DEFAULT_KEYS = {
    "global_win_rate": lambda: str(get_settings().global_win_rate),
    "spin_cooldown_seconds": lambda: str(get_settings().spin_cooldown_seconds),
    "max_daily_spins_per_user": lambda: str(get_settings().max_daily_spins_per_user),
}
CONTENT_SETTING_KEYS = ("links_json", "funnel_steps_json")


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


async def _cleanup_users(session: AsyncSession) -> None:
    await session.execute(delete(BotChatState))
    await session.execute(delete(SpinHistory))
    await session.execute(delete(UserConversion))
    await session.execute(delete(Referral))
    await session.execute(delete(User))


async def _cleanup_content(session: AsyncSession) -> None:
    blob_assets = (
        await session.execute(select(MediaAsset).where(MediaAsset.asset_type == MediaAssetType.url))
    ).scalars().all()
    for item in blob_assets:
        try:
            await delete_blob_object(item.value)
        except Exception:
            pass

    await session.execute(delete(MediaAsset))
    await session.execute(delete(AdminSettings).where(AdminSettings.key.in_(CONTENT_SETTING_KEYS)))


@router.get("")
async def settings_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    data = {}
    for key in DEFAULT_KEYS:
        data[key] = await _get_value(session, key)

    settings = get_settings()
    blob_enabled = blob_is_enabled()
    telegram_media_ready = bool(settings.bot_token.strip()) and settings.admin_tg_id > 0
    media_storage_ok = blob_enabled or telegram_media_ready
    if blob_enabled:
        media_storage_mode = "blob"
    elif telegram_media_ready:
        media_storage_mode = "telegram_file_id"
    else:
        media_storage_mode = "not_configured"

    return templates.TemplateResponse(
        request,
        "settings.html",
        {
            "request": request,
            "data": data,
            "db_url_masked": mask_database_url(settings.database_url),
            "db_is_ephemeral": is_ephemeral_database_url(settings.database_url),
            "blob_enabled": blob_enabled,
            "telegram_media_ready": telegram_media_ready,
            "media_storage_ok": media_storage_ok,
            "media_storage_mode": media_storage_mode,
            "msg": request.query_params.get("msg", ""),
            "error": request.query_params.get("error", ""),
        },
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
    return RedirectResponse(url="/admin/settings?msg=Настройки+сохранены", status_code=302)


@router.post("/cleanup/users")
async def cleanup_users(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    await _cleanup_users(session)
    await session.commit()
    return RedirectResponse(url="/admin/settings?msg=Пользователи+очищены", status_code=302)


@router.post("/cleanup/content")
async def cleanup_content(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    await _cleanup_content(session)
    await session.commit()
    await seed_defaults()
    return RedirectResponse(url="/admin/settings?msg=Контент+очищен+и+сброшен+к+дефолту", status_code=302)


@router.post("/cleanup/all")
async def cleanup_all(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    await _cleanup_users(session)
    await _cleanup_content(session)
    await session.commit()
    await seed_defaults()
    return RedirectResponse(url="/admin/settings?msg=База+очищена,+дефолты+восстановлены", status_code=302)
