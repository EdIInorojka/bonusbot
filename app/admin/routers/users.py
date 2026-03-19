from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.db.models.referral import Referral
from app.db.models.user import User


router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
async def users_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    users = (
        (
            await session.execute(select(User).order_by(User.created_at.desc()).limit(200))
        )
        .scalars()
        .all()
    )

    referral_counts = {}
    rows = await session.execute(
        select(Referral.referrer_id, Referral.level, func.count(Referral.id))
        .group_by(Referral.referrer_id, Referral.level)
    )
    for referrer_id, level, count in rows.all():
        referral_counts.setdefault(referrer_id, {1: 0, 2: 0, 3: 0, 4: 0, 5: 0})
        referral_counts[referrer_id][level] = count

    return templates.TemplateResponse(
        request,
        "users.html",
        {
            "request": request,
            "users": users,
            "referral_counts": referral_counts,
        },
    )
