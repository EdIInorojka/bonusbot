from __future__ import annotations

from typing import Any


DEFAULT_LINKS: dict[str, str] = {
    "channel": "https://t.me/your_channel",
    "registration": "https://example.com/register",
    "deposit": "https://example.com/deposit",
    "instruction": "https://example.com/instruction",
    "instruction_message": "📘 <b>How to use the bot</b>\n\n1) Register using our link.\n2) Complete your first deposit.\n3) Follow funnel steps and claim bonuses.",
    "bonus": "https://example.com/bonus",
    "signal": "https://example.com/signal",
    "webapp": "",
}


DEFAULT_FUNNEL_STEPS: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "Primary Registration",
        "slug": "primary_registration",
        "text": "Welcome!\n\nTo use the bot, subscribe to our channel first.",
        "photo": "",
        "buttons": [
            {"text": "Subscribe", "action": "url", "value": "channel"},
            {"text": "Check Subscription", "action": "callback", "value": "check_sub"},
        ],
    },
    {
        "step": 2,
        "title": "Main Menu",
        "slug": "main_menu",
        "text": "Main Menu\n\nWhat can this bot do?\n🎁 Claim bonuses every day\n▶ Follow the steps to unlock rewards",
        "photo": "",
        "buttons": [
            {"text": "📱 Register", "action": "url", "value": "registration"},
            {"text": "📘 Guide", "action": "callback", "value": "instruction"},
            {"text": "🎁 Claim Bonus", "action": "next", "value": "3"},
        ],
    },
    {
        "step": 3,
        "title": "Registration Check",
        "slug": "registration_check",
        "text": "Registration is not completed yet.\n\nUse promo code <b>honor17</b> during registration.\n\nAfter registration, you will receive an automatic update in the bot.",
        "photo": "",
        "buttons": [
            {"text": "🧩 Register Now", "action": "url", "value": "registration"},
            {"text": "⬅ Back to Main Menu", "action": "next", "value": "2"},
        ],
    },
    {
        "step": 4,
        "title": "First Deposit",
        "slug": "first_deposit",
        "text": "Registration completed!\n\nStep 2: make your first deposit.\n\nA higher deposit gives you a higher level and more high-probability signals.\n\nAfter the first deposit, you will receive an automatic update in the bot.",
        "photo": "",
        "buttons": [
            {"text": "💸 Make Deposit", "action": "url", "value": "deposit"},
            {"text": "⬅ Back to Main Menu", "action": "next", "value": "2"},
        ],
    },
    {
        "step": 5,
        "title": "Bonus Claim",
        "slug": "bonus_claim",
        "text": "Claim your bonuses right now.\n\nYou already got +70 free spins on multiple slots, and we also unlock a crypto giveaway for you.\n\nGet from 0.5 USDT up to 1 BTC.",
        "photo": "",
        "buttons": [
            {"text": "👉 Claim 70 FP", "action": "url", "value": "bonus"},
            {"text": "🎁 Claim Crypto Bonus", "action": "next", "value": "6"},
        ],
    },
    {
        "step": 6,
        "title": "Crypto Bonus",
        "slug": "crypto_bonus",
        "text": "You won 1 USDT, and this is just the beginning.\n\nClaim 1 USDT: https://t.me/huntzbtc/coin/55466\n\nSpin the free roulette and unlock even more bonuses.",
        "photo": "",
        "buttons": [
            {"text": "🎁 Open Mega Bonus", "action": "next", "value": "7"},
        ],
    },
    {
        "step": 7,
        "title": "Mega Slot Intro",
        "slug": "mega_slot_intro",
        "text": "Final stage unlocked.\n\nMega bonus is available now. Possible rewards:\n\n🍒 +5 spins\n🍒 Deposit bonus up to 32,000₽\n🍒 Voucher up to 70,000₽\n🍒 0.3 BTC\n🍒 500 FS",
        "photo": "",
        "buttons": [
            {"text": "🎰 Launch Slot", "action": "webapp", "value": "webapp"},
            {"text": "📣 Share Link", "action": "share", "value": "Join and claim a bonus: {link}"},
            {"text": "🚀 LuckyJet Signals", "action": "url", "value": "signal"},
        ],
    },
    {
        "step": 8,
        "title": "Post Win",
        "slug": "post_win",
        "text": "Mega bonus is now active for you.\n\nClaim it instantly and continue the flow to increase your rewards.",
        "photo": "",
        "buttons": [
            {"text": "👇 Claim Mega Bonus", "action": "webapp", "value": "webapp"},
            {"text": "💸 Deposit and Boost Bonus", "action": "url", "value": "deposit"},
        ],
    },
]