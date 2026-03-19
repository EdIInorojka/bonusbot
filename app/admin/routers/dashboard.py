from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.db.models.referral import Referral
from app.db.models.spin import SpinHistory
from app.db.models.user import User


router = APIRouter(prefix="/admin", tags=["admin-dashboard"])


@router.get("")
async def dashboard(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    users_count = (await session.scalar(select(func.count(User.id)))) or 0
    spins_count = (await session.scalar(select(func.count(SpinHistory.id)))) or 0
    wins_count = (await session.scalar(select(func.count(SpinHistory.id)).where(SpinHistory.won.is_(True)))) or 0
    referrals_count = (await session.scalar(select(func.count(Referral.id)))) or 0
    paid_total = (await session.scalar(select(func.coalesce(func.sum(SpinHistory.reward_value), 0.0)))) or 0.0

    level_rows = await session.execute(
        select(Referral.level, func.count(Referral.id)).group_by(Referral.level).order_by(Referral.level)
    )
    levels = {lvl: cnt for lvl, cnt in level_rows.all()}

    recent_spins = (
        (
            await session.execute(
                select(SpinHistory).order_by(SpinHistory.created_at.desc()).limit(15)
            )
        )
        .scalars()
        .all()
    )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "request": request,
            "users_count": users_count,
            "spins_count": spins_count,
            "wins_count": wins_count,
            "referrals_count": referrals_count,
            "paid_total": paid_total,
            "levels": levels,
            "recent_spins": recent_spins,
        },
    )


@router.get("/dashboard")
async def dashboard_alias() -> RedirectResponse:
    return RedirectResponse(url="/admin", status_code=302)
