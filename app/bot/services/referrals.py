from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.referral import Referral
from app.db.models.user import User


MAX_LEVEL = 5


async def attach_referrer(session: AsyncSession, user: User, referrer: User | None) -> None:
    if not referrer:
        return
    if user.referred_by_id is not None:
        return
    if user.id == referrer.id:
        return

    user.referred_by_id = referrer.id
    await session.flush()

    chain: list[int] = [referrer.id]
    parent_id = referrer.referred_by_id

    while parent_id and len(chain) < MAX_LEVEL:
        parent = await session.get(User, parent_id)
        if not parent:
            break
        chain.append(parent.id)
        parent_id = parent.referred_by_id

    for idx, referrer_id in enumerate(chain, start=1):
        exists = await session.execute(
            select(Referral).where(
                Referral.referrer_id == referrer_id,
                Referral.referral_id == user.id,
                Referral.level == idx,
            )
        )
        if exists.scalar_one_or_none() is not None:
            continue
        session.add(Referral(referrer_id=referrer_id, referral_id=user.id, level=idx))

    await session.flush()


async def referral_stats_by_level(session: AsyncSession, referrer_id: int) -> dict[int, int]:
    rows = await session.execute(
        select(Referral.level, Referral.id).where(Referral.referrer_id == referrer_id)
    )
    out: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for level, _ in rows:
        out[level] = out.get(level, 0) + 1
    return out
