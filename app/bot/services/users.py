import secrets
import string

from aiogram.types import User as TgUser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User


def generate_ref_code(size: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "REF" + "".join(secrets.choice(alphabet) for _ in range(size))


async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> User | None:
    result = await session.execute(select(User).where(User.id == tg_id))
    return result.scalar_one_or_none()


async def get_user_by_ref_code(session: AsyncSession, ref_code: str) -> User | None:
    result = await session.execute(select(User).where(User.ref_code == ref_code))
    return result.scalar_one_or_none()


async def get_or_create_user(session: AsyncSession, tg_user: TgUser) -> tuple[User, bool]:
    user = await get_user_by_tg_id(session, tg_user.id)
    created = False
    if user is None:
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name or "User",
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
            ref_code=generate_ref_code(),
        )
        session.add(user)
        await session.flush()
        created = True
    else:
        user.username = tg_user.username
        user.first_name = tg_user.first_name or user.first_name
        user.last_name = tg_user.last_name
        user.language_code = tg_user.language_code
    return user, created


async def set_funnel_step(session: AsyncSession, user: User, step: int) -> None:
    user.funnel_step = step
    await session.flush()
