from aiogram import F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import app.keyboards as keyboards

user_router = Router()

class Questions(StatesGroup):
    topic = State()
    text = State()
    file = State()

@user_router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Здравствуйте! Я - новостной бот. \n" \
                         "Для создания новости заполните форму:")
    await message.answer("Пункт 1. Название вашей новости:")
    await state.set_state(Questions.topic)

@user_router.message(Questions.topic)
async def start_command(message: Message, state: FSMContext):
    await state.update_data(q1=message.text)
    await message.answer("Пункт 2. Текст вашей новости:")
    await state.set_state(Questions.text)

@user_router.message(Questions.text)
async def start_command(message: Message, state: FSMContext):
    await state.update_data(q2=message.text)
    await message.answer("Пункт 3. Прикрепите файл:")
    await state.set_state(Questions.file)

@user_router.message(StateFilter(Questions.file), F.document | F.photo)
async def file_handler(message: Message, state: FSMContext):
    file_id = None
    file_name = None
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "Фото"

    await state.update_data(
        file_id=file_id,
        file_name=file_name
    )

    data = await state.get_data()

    result = (
        "Ваша новость: \n"
        f"Название: {data.get('q1', 'Не указано')} \n"
        f"Текст: {data.get('q2', 'Не указано')} \n"
        f"Файл: {file_name}"
    )

    if message.document:
        await message.answer_document(
            document=file_id,
            caption=result
        )

    elif message.photo:
        await message.answer_photo(
            photo=file_id,
            caption=result
        )

    await message("Новость отправлена на валидацию! Хотите создать ещё одну?")

    await state.clear()

@user_router.message(StateFilter(Questions.file))
async def wrong_file(message: Message):
    await message.answer("Неверный ввод! Прикрепите файл.")

@user_router.message(F.text == '')
async def make_another_news(message: Message):
    await message.answer('Выберите ответ:', reply_markup=keyboards.make_another_news)

@user_router.message()
async def any_command(message: Message):
    await message.answer("Неверная команда.")

""" 
сделать:
изменить введённые данные
удалить новость
"""