from __future__ import annotations

from typing import Any


DEFAULT_LINKS: dict[str, str] = {
    "channel": "https://t.me/your_channel",
    "registration": "https://1wcous.life/casino/list?open=register&sub1={source_id}",
    "deposit": "https://example.com/deposit",
    "instruction": "https://example.com/instruction",
    "instruction_message": (
        "🤖<b>Бот основан и обучен на кластерной нейронной сети OpenAI!</b>\n"
        "⚜️Для обучения бота было сыграно 🎰30,000 игр.\n\n"
        "В настоящее время пользователи бота успешно генерируют 15-25% от своего капитала ежедневно!\n\n"
        "Бот все еще проходит проверки и исправления! Точность бота составляет 92%!\n"
        "Чтобы достичь максимальной прибыли, следуйте этой инструкции:\n\n"
        "🟢 1. Зарегистрируйтесь в букмекерской конторе 1WIN: "
        "<a href=\"{registration_url}\">1WIN</a>\n"
        "[Если не открывается, воспользуйтесь VPN (Швеция).]\n"
        "❗️Без регистрации и промокода доступ к сигналам не будет открыт❗️\n\n"
        "🟢 2. Пополните баланс своего счета.\n"
        "🟢 3. Перейдите в раздел игр 1win и выберите игру.\n"
        "🟢 4. Установите количество ловушек на три. Это важно!\n"
        "🟢 5. Запросите сигнал у бота и ставьте ставки в соответствии с сигналами от бота.\n"
        "🟢 6. В случае неудачного сигнала рекомендуем удвоить (x²) вашу ставку."
    ),
    "bonus": "https://example.com/bonus",
    "signal": "https://example.com/signal",
    "webapp": "",
}


DEFAULT_FUNNEL_STEPS: list[dict[str, Any]] = [
    {
        "step": 1,
        "title": "Подписка",
        "slug": "primary_registration",
        "text": "Подпишитесь на канал, чтобы продолжить.",
        "photo": "",
        "buttons": [
            {"text": "📢 Подписаться", "action": "url", "value": "channel"},
            {"text": "✅ Проверить", "action": "callback", "value": "check_sub"},
        ],
    },
    {
        "step": 2,
        "title": "Главное меню",
        "slug": "main_menu",
        "text": "Главное меню\n\nВыберите действие:",
        "photo": "",
        "buttons": [
            {"text": "🧩 Регистрация", "action": "url", "value": "registration"},
            {"text": "📘 Инструкция", "action": "callback", "value": "instruction"},
            {"text": "🎁 Получить бонус", "action": "callback", "value": "claim_bonus"},
        ],
    },
    {
        "step": 3,
        "title": "Получение бонуса",
        "slug": "bonus_claim",
        "text": "✅ Регистрация подтверждена!\n\nНажмите кнопку ниже, чтобы получить бонус.",
        "photo": "",
        "buttons": [
            {"text": "🎁 Получить бонус", "action": "url", "value": "bonus"},
            {"text": "🎰 Запустить слот", "action": "webapp", "value": "webapp"},
            {"text": "⬅️ Главное меню", "action": "next", "value": "2"},
        ],
    },
    {
        "step": 4,
        "title": "Ошибка регистрации",
        "slug": "registration_error",
        "text": (
            "⚠️ Ошибка: Регистрация не пройдена!\n\n"
            "✦ При регистрации обязательно вводите промокод - 779931\n\n"
            "● После завершения регистрации, Вам автоматически придет уведомление в бота."
        ),
        "photo": "",
        "buttons": [
            {"text": "🧩 Зарегистрироваться", "action": "url", "value": "registration"},
            {"text": "🏠 Главное меню", "action": "next", "value": "2"},
        ],
    },
]
