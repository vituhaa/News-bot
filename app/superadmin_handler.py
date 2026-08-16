from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

from app.storage import storage
from app.models import Admin
import app.keyboards as keyboards

load_dotenv()

super_router = Router()
logger = logging.getLogger(__name__)

SUPER_ADMINS = os.getenv("SUPER_ADMINS", "")
super_admins_list = [x.strip() for x in SUPER_ADMINS.split(",") if x.strip()]

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)

class AdminState(StatesGroup):
    wait_for_choice = State()
    delete_admin = State()
    wait_for_comment = State()
    wait_for_channel = State()
    wait_for_user_id = State()

def is_superadmin(user_id: int) -> bool:
    return storage.is_superadmin(user_id) or (str(user_id) in super_admins_list)

@super_router.message(Command("super"))
async def start_super_admin(message: Message, state: FSMContext):
    user = message.from_user
    if is_superadmin(user.id):
        await message.answer("Выберите действие", reply_markup=keyboards.super_admin_keyboard)
        await state.set_state(AdminState.wait_for_choice)
    else:
        await message.answer("У вас нет прав суперадминистратора.")
        

@super_router.message(AdminState.wait_for_choice)
async def process_super_choice(message: Message, state: FSMContext):
    if message.text == "Добавить админа":
        await state.set_state(AdminState.wait_for_user_id)
        await message.answer(
            "Введите телеграм-ID нового администратора:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif message.text == "Список текущих админов":
        admins = storage.get_all_admins()
        if not admins:
            text = "Список администраторов пуст."
        else:
            text = "Список администраторов:\n"
            for i, admin in enumerate(admins, 1):
                role = "Суперадмин" if admin.role == 'superadmin' else "Админ"
                text += f"{i}. @{admin.username} (ID: {admin.user_id}) - {role}\n"
        await message.answer(text, reply_markup=keyboards.super_admin_keyboard)
        # await state.clear()
    elif message.text == "Удалить админа":
        await state.set_state(AdminState.delete_admin)
        await message.answer(
            "Удаление администратора.\n\nВведите Telegram ID пользователя, которого нужно удалить:"
        )
    elif message.text == "/admin" or message.text == "/start":
        await message.answer(
            "Вы ввели новую команду",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "Неверная команда. Выберите из предложенных кнопок.",
            reply_markup=keyboards.super_admin_keyboard
        )

@super_router.message(AdminState.delete_admin)
async def process_delete_admin(message: Message, state: FSMContext):
    try:
        delete_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ввод! Введите числовой ID (например, 123456789):")
        return
    
    if not storage.get_admin(delete_admin_id):
        await message.answer(
            "Этот пользователь не является администратором.",
            reply_markup=keyboards.super_admin_keyboard
        )
        await state.set_state(AdminState.wait_for_choice)
        return
    
    storage.remove_admin(delete_admin_id)
    await message.answer(
        f"Администратор удалён: {delete_admin_id}",
        reply_markup=keyboards.super_admin_keyboard
    )
    await state.set_state(AdminState.wait_for_choice)


@super_router.message(AdminState.wait_for_user_id)
async def process_new_admin(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ввод! Введите числовой ID (например, 123456789):")
        return

    if storage.get_admin(new_admin_id):
        await message.answer(
            "Этот пользователь уже является администратором.",
            reply_markup=keyboards.super_admin_keyboard
        )
        await state.set_state(AdminState.wait_for_choice)
        return

    admin = Admin(
        user_id=new_admin_id,
        username=f"id_{new_admin_id}",
        role='admin',
        added_by=message.from_user.id
    )
    storage.add_admin(admin)

    await message.answer(
        f"Новый администратор добавлен: {new_admin_id}",
        reply_markup=keyboards.super_admin_keyboard
    )
    await state.set_state(AdminState.wait_for_choice)