from aiogram.fsm.state import State, StatesGroup


class FunnelStates(StatesGroup):
    waiting_subscription = State()
    in_funnel = State()
    waiting_webapp_result = State()
