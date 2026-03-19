from dataclasses import dataclass


@dataclass(frozen=True)
class FunnelButton:
    text: str
    action: str
    value: str


@dataclass(frozen=True)
class FunnelStep:
    step: int
    text: str
    buttons: tuple[FunnelButton, ...]


FUNNEL_STEPS: dict[int, FunnelStep] = {
    1: FunnelStep(
        step=1,
        text=(
            "Добро пожаловать, Илья!\n\n"
            "Для использования бота - подпишись на наш канал \U0001F91D"
        ),
        buttons=(
            FunnelButton("Подписаться", "url", "channel"),
            FunnelButton("Проверить", "callback", "check_sub"),
        ),
    ),
    2: FunnelStep(
        step=2,
        text=(
            "Главное меню:\n\n"
            "What can this bot do?\n"
            "\U0001F381 Забирай бонуси каждый день\n"
            "\U0001F449 Просто жми /start"
        ),
        buttons=(
            FunnelButton("\U0001F4F1 Регистрация", "url", "registration"),
            FunnelButton("\U0001F3B0 Инструкция", "url", "instruction"),
            FunnelButton("\U0001F310 Выбрать язык", "callback", "lang"),
            FunnelButton("\U0001F381 Получить Бонуску", "next", "3"),
        ),
    ),
    3: FunnelStep(
        step=3,
        text=(
            "\u26A0\uFE0F Ошибка: Регистрация не пройдена!\n\n"
            "\u25B6 При регистрации обязательно вводите промокод - honor17\n\n"
            "• После завершения регистрации, Вам автоматически придет уведомление в бота."
        ),
        buttons=(
            FunnelButton("\U0001F9E9 Зарегистрироваться", "url", "registration"),
            FunnelButton("\U0001F6CD Вернуться в главное меню", "next", "2"),
        ),
    ),
    4: FunnelStep(
        step=4,
        text=(
            "Поздравляем с успешной регистрацией! \U0001F973\n\n"
            "\U0001F525Шаг 2 - Внеси первый депозит.\n\n"
            "♦ Чем больше депозит, тем больше УРОВЕНЬ в боте, а чем больше уровень в боте, тем больше количество сигналов с высокой вероятностью проходимости сигнала ты будешь получать.\n\n"
            "• После пополнения первого депозита, Вам автоматически придет уведомление в бота."
        ),
        buttons=(
            FunnelButton("\U0001F4B8 Внести депозит", "url", "deposit"),
            FunnelButton("\U0001F6CD Вернуться в главное меню", "next", "2"),
        ),
    ),
    5: FunnelStep(
        step=5,
        text=(
            "\U0001F525 ЗАБИРАЙ СВОИ БОНУСЫ ПРЯМО СЕЙЧАС\n\n"
            "По мимо того что ты выиграл +70 фриспинов на более чем 10 разных слотах, мы ДАРИМ тебе еще 1 акцию в виде раздачи криптовалюты!\n\n"
            "\U0001F447 Забирай прямо сейчас от 0.5 USDT до 1 BTC!"
        ),
        buttons=(
            FunnelButton("\U0001F449 Получить 70 FP", "url", "bonus"),
            FunnelButton("\U0001F381 Забрать Крипто-бонус", "next", "6"),
        ),
    ),
    6: FunnelStep(
        step=6,
        text=(
            "\U0001F4AA ТЫ ВЫИГРАЛ 1 USDT, НО ЭТО ЕЩЕ НЕ ВСЕ...\n\n"
            "\U0001FAF4 Забрать 1 USDT: https://t.me/huntzbtc/coin/55466\n\n"
            "Крути БЕСПЛАТНУЮ рулетку получи ЕЩЕ БОЛЬШЕ БОНУСОВ в нашей МЕГА-БОНУСКЕ - бесплатно, прямо сейчас"
        ),
        buttons=(
            FunnelButton("\U0001F381 Выиграть Мега-Бонуску", "next", "7"),
        ),
    ),
    7: FunnelStep(
        step=7,
        text=(
            "\u2705 НУ ВОТ И ВСЕ! ТЫ НА ФИНИШНОЙ ПРЯМОЙ!\n\n"
            "Мега бонуска доступна уже сейчас! Ты можешь выиграть невероятно много и вот что именно:\n\n"
            "\U0001F352\U0001F352\U0001F352 +5 спинов\n"
            "\U0001F352\U0001F352\U0001F352 Бонуска за 32,000\u20BD\n"
            "\U0001F352\U0001F352\U0001F352 Ваучер на 70,000\u20BD\n"
            "\U0001F352\U0001F352\U0001F352 0.3 BTC\n"
            "\U0001F352\U0001F352\U0001F352 500 FS"
        ),
        buttons=(
            FunnelButton("\U0001F3B0 Запустить слот", "webapp", "webapp"),
            FunnelButton("\U0001F4E3 Поделиться ссылкой", "share", "share"),
            FunnelButton("\U0001F680 Сигналы LuckyJet", "url", "signal"),
        ),
    ),
    8: FunnelStep(
        step=8,
        text=(
            "\U0001F680 С ЭТОЙ БОНУСКОЙ ТЕБЯ ЖДЕМ МЕГА-ЗАНОСЫ!!\n\n"
            "Как и все что ты получал ранее, данную бонуску ты получишь моментально на нашем крутить."
        ),
        buttons=(
            FunnelButton("\U0001F447 Получить Мега-Бонуску", "webapp", "webapp"),
            FunnelButton("\U0001F4B8 Сделать Депозит и получить МЕГА БОНУСКУ", "url", "deposit"),
        ),
    ),
}


def get_step(step_id: int) -> FunnelStep:
    if step_id not in FUNNEL_STEPS:
        return FUNNEL_STEPS[max(FUNNEL_STEPS)]
    return FUNNEL_STEPS[step_id]
