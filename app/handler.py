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

def check_input_type(message: Message) -> tuple[bool, str]:
    allowed = {
        'document': ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
        'photo': ['image/jpg', 'image/png']
    }

    if message.document:
        doc_type = message.document.mime_type
        if doc_type in allowed['document']:
            return True, ""
        else:
            return False, "Неверный ввод! Прикрепите PDF или DOCX файл или прикрепите до 10 фотографий."
    elif message.photo:
        return True, ""
    return False, ""


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

    is_allowed, output = check_input_type(message)
    if not is_allowed:
        await message.answer(output)
        return
    else:
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
    
        await message.answer("Новость отправлена на валидацию! Хотите создать ещё одну?")

    await state.clear()

@user_router.message(F.text == '')
async def make_another_news(message: Message):
    await message.answer('Выберите ответ:', reply_markup=keyboards.make_another_news)

@user_router.message()
async def any_command(message: Message):
    await message.answer("Неверная команда.")
