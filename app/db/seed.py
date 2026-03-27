import asyncio
import json

from sqlalchemy import select

from app.bot.content_defaults import DEFAULT_FUNNEL_STEPS, DEFAULT_LINKS
from app.core.config import build_webapp_url, get_settings
from app.db.models.admin_settings import AdminSettings
from app.db.models.prize import Prize, PrizeType
from app.db.session import AsyncSessionLocal


DEFAULT_PRIZES = [
    {
        "name": "+5 спинов",
        "display_text": "+5 спинов",
        "prize_type": PrizeType.free_spins,
        "value": 5,
        "weight": 40,
    },
    {
        "name": "Бонус 32,000₽",
        "display_text": "Бонуска за 32,000₽",
        "prize_type": PrizeType.deposit_bonus,
        "value": 32000,
        "weight": 25,
    },
    {
        "name": "Ваучер 70,000₽",
        "display_text": "Ваучер на 70,000₽",
        "prize_type": PrizeType.promo_code,
        "value": 70000,
        "weight": 15,
    },
    {
        "name": "0.3 BTC",
        "display_text": "0.3 BTC",
        "prize_type": PrizeType.custom,
        "value": 0.3,
        "weight": 5,
    },
    {
        "name": "500 FS",
        "display_text": "500 FS",
        "prize_type": PrizeType.fp,
        "value": 500,
        "weight": 15,
    },
]

MIGRATION_KEY = "migration_mines_webapp_v1"
MINES_BUTTON = {"text": "Mines Predictions", "action": "webapp", "value": "mines_webapp"}


def _default_links(settings) -> dict[str, str]:
    default_links = dict(DEFAULT_LINKS)
    default_links.update(
        {
            "channel": settings.channel_url,
            "registration": settings.registration_url,
            "deposit": settings.deposit_url,
            "instruction": settings.instruction_url,
            "instruction_message": settings.instruction_message,
            "bonus": settings.bonus_claim_url,
            "signal": settings.signal_url,
            "webapp": build_webapp_url(),
            "mines_webapp": build_webapp_url("/mines"),
        }
    )
    return default_links


def _ensure_mines_button(steps: list[dict]) -> list[dict]:
    target = None
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("slug", "")).strip() == "bonus_claim":
            target = step
            break
    if target is None:
        return steps

    buttons = target.get("buttons")
    if not isinstance(buttons, list):
        buttons = []
        target["buttons"] = buttons

    already_exists = any(
        isinstance(btn, dict)
        and str(btn.get("action", "")).strip() == "webapp"
        and str(btn.get("value", "")).strip() == "mines_webapp"
        for btn in buttons
    )
    if already_exists:
        return steps

    insert_at = next(
        (
            idx
            for idx, btn in enumerate(buttons)
            if isinstance(btn, dict) and str(btn.get("action", "")).strip() == "next"
        ),
        len(buttons),
    )
    buttons.insert(insert_at, dict(MINES_BUTTON))
    return steps


async def seed() -> None:
    settings = get_settings()
    default_links = _default_links(settings)

    async with AsyncSessionLocal() as session:
        exists = (await session.execute(select(Prize.id).limit(1))).first()
        if not exists:
            for payload in DEFAULT_PRIZES:
                session.add(Prize(**payload))

        for key, value in {
            "global_win_rate": "0.35",
            "spin_cooldown_seconds": "300",
            "max_daily_spins_per_user": "20",
            "links_json": json.dumps(default_links, ensure_ascii=False),
            "funnel_steps_json": json.dumps(DEFAULT_FUNNEL_STEPS, ensure_ascii=False),
        }.items():
            row = await session.get(AdminSettings, key)
            if not row:
                session.add(AdminSettings(key=key, value=value))

        migration_row = await session.get(AdminSettings, MIGRATION_KEY)
        if not migration_row:
            links_row = await session.get(AdminSettings, "links_json")
            if links_row:
                try:
                    links_payload = json.loads(links_row.value)
                except Exception:
                    links_payload = {}
                if not isinstance(links_payload, dict):
                    links_payload = {}
                if not str(links_payload.get("mines_webapp", "")).strip():
                    links_payload["mines_webapp"] = build_webapp_url("/mines")
                    links_row.value = json.dumps(links_payload, ensure_ascii=False)

            steps_row = await session.get(AdminSettings, "funnel_steps_json")
            if steps_row:
                try:
                    steps_payload = json.loads(steps_row.value)
                except Exception:
                    steps_payload = []
                if isinstance(steps_payload, list):
                    _ensure_mines_button(steps_payload)
                    steps_row.value = json.dumps(steps_payload, ensure_ascii=False)

            session.add(AdminSettings(key=MIGRATION_KEY, value="1"))

        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
