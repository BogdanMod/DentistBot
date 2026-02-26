"""FSM состояния для диалогов"""
from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния регистрации пользователя"""
    waiting_for_confirmation = State()