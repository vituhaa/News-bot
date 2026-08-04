import os
from aiogram import Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import app.keyboards as keyboards
from dotenv import load_dotenv

load_dotenv()
SUPER_ADMIN = os.getenv('SUPER_ADMIN')

super_admin_router = Router()

class SuperAdminState(StatesGroup):
    wait_for_choice = State()
    wait_for_new_admin = State()

def is_super_admin(user_id: int) -> bool:
    if str(user_id) == SUPER_ADMIN:
        return True
    else:
        return False

@super_admin_router.message(Command("super"))
async def start_super_admin(message: Message, state: FSMContext):
    user = message.from_user
    if is_super_admin(user.id):
        await message.answer("Выберите действие", reply_markup=keyboards.super_admin_keyboard)
        await state.set_state(SuperAdminState.wait_for_choice)
    else:
        await message.answer("У вас нет прав администратора.")
        return
    

@super_admin_router.message(SuperAdminState.wait_for_choice)
async def process_choce(message: Message, state: FSMContext):
    if message.text == "Добавить админа":
        await state.set_state(SuperAdminState.wait_for_new_admin)
        await message.answer("Введите ник (@username) или телеграм-ID: ", reply_markup=ReplyKeyboardRemove())
    elif message.text == "Список текущих админов":
        await message.answer("Список администраторов: \n"
                             "1. a \n"
                             "2. b \n"
                             "3. c \n", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Неверная команда. Выберите любую из предложенных в клавиатуре.")
        return


@super_admin_router.message(SuperAdminState.wait_for_new_admin)
async def process_name(message: Message, state: FSMContext):
    name = message.text
    if not name.startswith("@"):
        if not (8 <= len(name) <= 10):
            await message.answer("Неверный ввод! Попробуйте ввести ник или ID профиля как в примере. \n"
                                    "Пример: ник - @username или числовое ID длиной от 8 до 10 цифр.")
            return
        
    await message.answer(f"Новый администратор добавлен: {name}", reply_markup=ReplyKeyboardRemove())
    await state.clear()

