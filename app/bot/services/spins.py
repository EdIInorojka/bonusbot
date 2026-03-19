import json
import logging
import random
from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.admin_settings import AdminSettings
from app.db.models.prize import Prize
from app.db.models.spin import SpinHistory
from app.db.models.user import User


class SpinService:
    def __init__(self, redis: Redis | None):
        self.redis = redis
        self.settings = get_settings()

    @staticmethod
    async def get_admin_value(session: AsyncSession, key: str, default: str) -> str:
        row = await session.get(AdminSettings, key)
        if not row:
            return default
        return row.value

    async def get_win_rate(self, session: AsyncSession) -> float:
        value = await self.get_admin_value(
            session,
            "global_win_rate",
            str(self.settings.global_win_rate),
        )
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return self.settings.global_win_rate

    async def get_cooldown(self, session: AsyncSession) -> int:
        value = await self.get_admin_value(
            session,
            "spin_cooldown_seconds",
            str(self.settings.spin_cooldown_seconds),
        )
        try:
            return max(30, int(value))
        except ValueError:
            return self.settings.spin_cooldown_seconds

    async def get_daily_limit(self, session: AsyncSession) -> int:
        value = await self.get_admin_value(
            session,
            "max_daily_spins_per_user",
            str(self.settings.max_daily_spins_per_user),
        )
        try:
            return max(1, int(value))
        except ValueError:
            return self.settings.max_daily_spins_per_user

    async def cooldown_left(self, user_id: int, ip: str | None) -> int:
        if not self.redis:
            return 0

        keys = [f"spin:cooldown:user:{user_id}"]
        if ip:
            keys.append(f"spin:cooldown:ip:{ip}")

        ttls: list[int] = []
        for key in keys:
            try:
                ttl = await self.redis.ttl(key)
            except Exception:
                logging.exception("Failed to read cooldown TTL from Redis")
                continue
            if ttl and ttl > 0:
                ttls.append(ttl)

        return max(ttls) if ttls else 0

    async def _check_daily_limit(self, session: AsyncSession, user_id: int) -> bool:
        limit = await self.get_daily_limit(session)
        start_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        count = await session.scalar(
            select(func.count(SpinHistory.id)).where(
                and_(SpinHistory.user_id == user_id, SpinHistory.created_at >= start_day)
            )
        )
        return (count or 0) < limit

    async def _check_prize_limits(self, session: AsyncSession, user_id: int, prize: Prize) -> bool:
        start_day = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        if prize.daily_limit is not None:
            day_count = await session.scalar(
                select(func.count(SpinHistory.id)).where(
                    and_(SpinHistory.prize_id == prize.id, SpinHistory.created_at >= start_day)
                )
            )
            if (day_count or 0) >= prize.daily_limit:
                return False

        if prize.per_user_limit is not None:
            user_count = await session.scalar(
                select(func.count(SpinHistory.id)).where(
                    and_(SpinHistory.prize_id == prize.id, SpinHistory.user_id == user_id)
                )
            )
            if (user_count or 0) >= prize.per_user_limit:
                return False

        return True

    async def choose_prize(self, session: AsyncSession, user_id: int) -> Prize | None:
        if not await self._check_daily_limit(session, user_id):
            return None

        prizes = (await session.execute(select(Prize).where(Prize.is_active.is_(True)))).scalars().all()
        if not prizes:
            return None

        win_rate = await self.get_win_rate(session)
        if random.random() > win_rate:
            return None

        filtered: list[Prize] = []
        weights: list[float] = []
        for prize in prizes:
            if await self._check_prize_limits(session, user_id, prize):
                filtered.append(prize)
                weights.append(max(prize.weight, 0.0))

        if not filtered or sum(weights) <= 0:
            return None
        return random.choices(filtered, weights=weights, k=1)[0]

    async def save_spin(
        self,
        session: AsyncSession,
        user: User,
        prize: Prize | None,
        ip: str | None,
        user_agent: str | None,
        session_key: str | None,
        payload: dict,
    ) -> SpinHistory:
        cooldown = await self.get_cooldown(session)
        cooldown_until = datetime.now(UTC) + timedelta(seconds=cooldown)

        spin = SpinHistory(
            user_id=user.id,
            prize_id=prize.id if prize else None,
            won=bool(prize),
            reward_value=prize.value if prize else 0,
            source_ip=ip,
            user_agent=user_agent,
            cooldown_until=cooldown_until,
            session_key=session_key,
            payload=payload,
            spin_no=user.total_spins + 1,
        )
        session.add(spin)

        user.total_spins += 1
        if prize:
            user.balance += prize.value

        await session.flush()

        if self.redis:
            try:
                await self.redis.setex(f"spin:cooldown:user:{user.id}", cooldown, "1")
                if ip:
                    await self.redis.setex(f"spin:cooldown:ip:{ip}", cooldown, "1")
            except Exception:
                logging.exception("Failed to write cooldown keys to Redis")

        return spin


def serialize_spin_result(spin: SpinHistory, prize: Prize | None) -> str:
    data = {
        "spin_id": spin.id,
        "won": spin.won,
        "prize_id": prize.id if prize else None,
        "prize": prize.display_text if prize else "No win",
        "reward_value": spin.reward_value,
        "spin_no": spin.spin_no,
    }
    return json.dumps(data, ensure_ascii=False)
