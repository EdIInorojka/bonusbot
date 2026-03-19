from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin, templates
from app.db.models.prize import Prize, PrizeType


router = APIRouter(prefix="/admin/prizes", tags=["admin-prizes"])


@router.get("")
async def prizes_page(
    request: Request,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    prizes = (await session.execute(select(Prize).order_by(Prize.id.asc()))).scalars().all()
    return templates.TemplateResponse(
        request,
        "prizes.html",
        {
            "request": request,
            "prizes": prizes,
            "prize_types": [p.value for p in PrizeType],
        },
    )


@router.post("/create")
async def create_prize(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
    name: str = Form(...),
    display_text: str = Form(...),
    prize_type: str = Form("custom"),
    value: float = Form(0),
    weight: float = Form(1),
    daily_limit: int | None = Form(default=None),
    per_user_limit: int | None = Form(default=None),
):
    prize = Prize(
        name=name,
        display_text=display_text,
        prize_type=PrizeType(prize_type),
        value=value,
        weight=weight,
        daily_limit=daily_limit,
        per_user_limit=per_user_limit,
    )
    session.add(prize)
    await session.commit()
    return RedirectResponse(url="/admin/prizes", status_code=302)


@router.post("/{prize_id}/toggle")
async def toggle_prize(
    prize_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    prize = await session.get(Prize, prize_id)
    if prize:
        prize.is_active = not prize.is_active
        await session.commit()
    return RedirectResponse(url="/admin/prizes", status_code=302)


@router.post("/{prize_id}/delete")
async def delete_prize(
    prize_id: int,
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    prize = await session.get(Prize, prize_id)
    if prize:
        await session.delete(prize)
        await session.commit()
    return RedirectResponse(url="/admin/prizes", status_code=302)
