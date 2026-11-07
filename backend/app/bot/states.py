from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Talabani universitet/fakultet/guruhga bog'lash uchun bosqichma-bosqich oqim"""
    waiting_university = State()
    waiting_faculty = State()
    waiting_group = State()


class ReminderStates(StatesGroup):
    """Dars eslatmasi necha daqiqa oldin yuborilishini so'rash oqimi"""
    waiting_minutes = State()
