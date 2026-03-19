from urllib.parse import quote_plus

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.services.content import DynamicFunnelStep, get_links_config
from app.bot.services.funnel import build_ref_link
from app.db.models.user import User



def _resolve_url(value: str, links: dict[str, str]) -> str:
    raw = value.strip()
    if raw in links:
        return links[raw]

    if raw.startswith("http://") or raw.startswith("https://") or raw.startswith("t.me/"):
        return raw

    return raw


async def step_keyboard(
    session: AsyncSession,
    user: User,
    step: DynamicFunnelStep,
    _step_ids: list[int],
) -> InlineKeyboardMarkup:
    links = await get_links_config(session)
    rows: list[list[InlineKeyboardButton]] = []

    for button in step.buttons:
        if button.action == "url":
            rows.append([InlineKeyboardButton(text=button.text, url=_resolve_url(button.value, links))])
        elif button.action == "webapp":
            webapp_url = f"{_resolve_url(button.value, links)}?startapp={user.ref_code}"
            rows.append([InlineKeyboardButton(text=button.text, web_app=WebAppInfo(url=webapp_url))])
        elif button.action == "callback":
            rows.append([InlineKeyboardButton(text=button.text, callback_data=f"funnel:{button.value}")])
        elif button.action == "next":
            rows.append([InlineKeyboardButton(text=button.text, callback_data=f"funnel:next:{button.value}")])
        elif button.action == "share":
            ref_link = build_ref_link(user)
            share_template = button.value.strip() if button.value.strip() else "Join and claim a bonus: {link}"
            share_text = quote_plus(share_template.replace("{link}", ref_link))
            rows.append(
                [
                    InlineKeyboardButton(
                        text=button.text,
                        url=f"https://t.me/share/url?url={quote_plus(ref_link)}&text={share_text}",
                    )
                ]
            )

    return InlineKeyboardMarkup(inline_keyboard=rows)
