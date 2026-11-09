from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Talabani universitet/fakultet/guruhga bog'lash uchun bosqichma-bosqich oqim"""
    waiting_university = State()
    waiting_faculty = State()
    waiting_group = State()
    waiting_schedule = State()  # guruh jadvali yo'q: rasm yoki matn kutilmoqda


class ReminderStates(StatesGroup):
    """Dars eslatmasi necha daqiqa oldin yuborilishini so'rash oqimi"""
    waiting_minutes = State()


class ContactStates(StatesGroup):
    """Talaba adminga murojaat yozishi va admin javob yozishi"""
    waiting_message = State()
    waiting_admin_reply = State()


class AnnouncementStates(StatesGroup):
    """Admin e'lon matnini yozish oqimi"""
    waiting_text = State()


class TeacherStates(StatesGroup):
    """O'qituvchi ro'yxatdan o'tishi va jadval yuborishi"""
    waiting_university = State()
    waiting_name = State()
    waiting_department = State()
    waiting_schedule = State()
