from app.bot.services.content import DynamicFunnelStep, next_step_id, prev_step_id, step_position
from app.core.config import get_settings
from app.db.models.user import User


def build_ref_link(user: User) -> str:
    settings = get_settings()
    return f"https://t.me/{settings.bot_username}?start={user.ref_code}"


def render_step_text(user: User, step: DynamicFunnelStep, steps: list[DynamicFunnelStep]) -> str:
    link = build_ref_link(user)
    pos, total = step_position(step, steps)
    return f"{step.text}\n\n🔗 Your referral link:\n{link}\n\nStep {pos}/{total}"


def next_step(current_step_id: int, steps: list[DynamicFunnelStep]) -> int:
    return next_step_id(current_step_id, steps)


def prev_step(current_step_id: int, steps: list[DynamicFunnelStep]) -> int:
    return prev_step_id(current_step_id, steps)
