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

def is_admin(user_id: int) -> bool:
    if str(user_id) == ADMIN:
        return True
    else:
        return False

@admin_router.message(Command("admin"))
async def start_admin(message: Message, state: FSMContext):
    user = message.from_user
    # await state.clear()
    print("USER ID TYPE:", type(user.id))
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

# @admin_router.message(AdminState.wait_for_choice)
# async def confirm_message(message: Message, state: FSMContext):
#     if message.text == "Одобрить":
#         await state.clear()
#         await message.answer("Редактируем...", reply_markup=ReplyKeyboardRemove())
#         await message.answer("Пункт 1. Название вашей новости:")
#         await state.set_state(Questions.topic)
#     elif message.text == "Вернуть на доработку":
#         await state.clear()
#         await message.answer("Готово! Новость отправлена на валидацию!", reply_markup=ReplyKeyboardRemove())
#     else:
#         await message.answer("Введите ответ с помощью клавиатуры.", reply_markup=keyboards.edit_news)


