# app/fsm_states.py
from aiogram.fsm.state import StatesGroup, State

class ProfileStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_dob = State()

class ImageUploadState(StatesGroup):
    waiting_for_dict_choice = State()
    waiting_for_photo = State()

class ProfileChoiceState(StatesGroup):
    waiting_for_theme_choice = State()
    waiting_for_tarot_choice = State()

class Form(StatesGroup):
    id_to_msg = State()
    text_msg_for_one_user = State()
    text_msg_for_all_users = State()
    waiting_for_confirmation = State()

class MemeCreation(StatesGroup):
    waiting_for_text = State()