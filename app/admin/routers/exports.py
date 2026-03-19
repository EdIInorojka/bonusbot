from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin.deps import db_session, require_admin
from app.db.models.spin import SpinHistory
from app.db.models.user import User


router = APIRouter(prefix="/admin/export", tags=["admin-export"])


@router.get("/users.xlsx")
async def export_users(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    users = (await session.execute(select(User).order_by(User.created_at.desc()))).scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Users"
    ws.append(["user_id", "username", "name", "ref_code", "referred_by", "balance", "spins", "created_at"])

    for user in users:
        ws.append([
            user.id,
            user.username,
            f"{user.first_name} {user.last_name or ''}".strip(),
            user.ref_code,
            user.referred_by_id,
            user.balance,
            user.total_spins,
            user.created_at.isoformat() if user.created_at else "",
        ])

    file_obj = BytesIO()
    wb.save(file_obj)
    file_obj.seek(0)
    return StreamingResponse(
        file_obj,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=users.xlsx"},
    )


@router.get("/spins.xlsx")
async def export_spins(
    _: str = Depends(require_admin),
    session: AsyncSession = Depends(db_session),
):
    spins = (await session.execute(select(SpinHistory).order_by(SpinHistory.created_at.desc()))).scalars().all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Spins"
    ws.append(["spin_id", "user_id", "won", "prize_id", "reward", "ip", "created_at"])

    for spin in spins:
        ws.append([
            spin.id,
            spin.user_id,
            int(spin.won),
            spin.prize_id,
            spin.reward_value,
            spin.source_ip,
            spin.created_at.isoformat() if spin.created_at else "",
        ])

    file_obj = BytesIO()
    wb.save(file_obj)
    file_obj.seek(0)
    return StreamingResponse(
        file_obj,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=spins.xlsx"},
    )
