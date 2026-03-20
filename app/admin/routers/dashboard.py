from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.db.models.user import User
from app.db.models.user_conversion import UserConversion


router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


def _is_new_user(created_at: datetime | None, cutoff_utc: datetime) -> bool:
    if not created_at:
        return False
    if created_at.tzinfo is None:
        return created_at >= cutoff_utc.replace(tzinfo=None)
    return created_at >= cutoff_utc


@router.get("")
async def dashboard(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    now_utc = datetime.now(timezone.utc)
    new_cutoff = now_utc - timedelta(hours=24)

    users_count = (await session.scalar(select(func.count(User.id)))) or 0
    new_users_24h = (
        await session.scalar(select(func.count(User.id)).where(User.created_at >= new_cutoff))
    ) or 0
    registered_count = (
        await session.scalar(
            select(func.count(UserConversion.user_id)).where(UserConversion.is_registered.is_(True))
        )
    ) or 0
    first_deposit_count = (
        await session.scalar(
            select(func.count(UserConversion.user_id)).where(UserConversion.has_first_deposit.is_(True))
        )
    ) or 0

    conversion_rows = (
        await session.execute(
            select(User, UserConversion)
            .outerjoin(UserConversion, UserConversion.user_id == User.id)
            .order_by(User.created_at.desc())
            .limit(300)
        )
    ).all()

    users_view = []
    for user, conversion in conversion_rows:
        users_view.append(
            {
                "id": user.id,
                "username": user.username or "",
                "name": f"{user.first_name} {user.last_name or ''}".strip(),
                "created_at": user.created_at,
                "is_new": _is_new_user(user.created_at, new_cutoff),
                "is_registered": bool(conversion and conversion.is_registered),
                "registration_at": conversion.registration_confirmed_at if conversion else None,
                "has_first_deposit": bool(conversion and conversion.has_first_deposit),
                "first_deposit_at": conversion.first_deposit_confirmed_at if conversion else None,
                "first_deposit_amount": conversion.first_deposit_amount if conversion else None,
            }
        )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "users_count": users_count,
            "new_users_24h": new_users_24h,
            "registered_count": registered_count,
            "first_deposit_count": first_deposit_count,
            "users_view": users_view,
        },
    )


@router.get("/dashboard")
async def dashboard_alias() -> RedirectResponse:
    return RedirectResponse(url="/admin", status_code=302)
