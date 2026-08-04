import os
from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import app.keyboards as keyboards
from dotenv import load_dotenv

load_dotenv()
ADMIN = os.getenv('ADMIN')

admin_router = Router()

class AdminState(StatesGroup):
    wait_for_choice = State()
    wait_for_channel_link = State()

def is_admin(user_id: int) -> bool:
    if str(user_id) == ADMIN:
        return True
    else:
        return False

@admin_router.message(Command("admin"))
async def start_admin(message: Message, state: FSMContext):
    user = message.from_user
    if is_admin(user.id):
        await message.answer("Пришла новость! \n"
                            f"От: ываыва \n"
                            f"Название: ррр \n"
                            f"Текст: hhh \n"
                            f"Тег: hhhh \n"
                            f"Файлы: jj", reply_markup=keyboards.admin_keyboard)
        
        await state.set_state(AdminState.wait_for_choice)
    else:
        await message.answer("У вас нет прав администратора.")
        return
    

@admin_router.message(AdminState.wait_for_choice)
async def confirm_message(message: Message, state: FSMContext):
    if message.text == "Одобрить":
        await state.set_state(AdminState.wait_for_channel_link)
        await message.answer("Введите ссылку на телеграм-канал, где хотите опубликовать новость:", reply_markup=ReplyKeyboardRemove())
    elif message.text == "Вернуть на доработку":
        await state.clear()
        await message.answer("Отправляем на доработку...", reply_markup=ReplyKeyboardRemove())
    elif message.text == "Удалить":
        await state.clear()
        await message.answer("Новость удалена.", reply_markup=ReplyKeyboardRemove())


@admin_router.message(AdminState.wait_for_channel_link) # нужно, чтобы она сохранялась между сессиями (+добавить возможность поменять в любой момент)
async def process_channel_link(message: Message, state: FSMContext):
    link = message.text
    if not link.startswith(("https://t.me/", "@")):
        await message.answer("Неверный ввод! Попробуйте ввести ссылку или название как в примере. \n"
                             "Пример: https://t.me/newsbottest100 или @newsbottest100")
        return
    await message.answer(f"Новость опубликована в канале: {link}", reply_markup=ReplyKeyboardRemove())
    await state.clear()

