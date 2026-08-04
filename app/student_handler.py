from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import app.keyboards as keyboards

user_router = Router()

"""
заглушки для бд: 
1) статус новости студента (создание новости в бд)
2) сохранённые данные новости для последующего редактирования - user_news = {}
"""

class Questions(StatesGroup):
    topic = State()
    text = State()
    tags = State()
    file = State()

class UserState(StatesGroup):
    wait_for_choice = State()

user_news = {} # удалить потом и заменить на таблицу с новостями

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
                         "Для создания новости заполните форму:", reply_markup=ReplyKeyboardRemove())
    await message.answer("Пункт 1. Название вашей новости:")
    await state.set_state(Questions.topic)


@user_router.message(Questions.topic)
async def type_text(message: Message, state: FSMContext):
    await state.update_data(q1=message.text)
    if (len(message.text) < 200):
        await message.answer("Пункт 2. Текст вашей новости:")
    else:
        await message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
        return
    await state.set_state(Questions.text)   


@user_router.message(Questions.text)
async def type_tags(message: Message, state: FSMContext):
    await message.answer("Пункт 3. Тэг вашей новости:", reply_markup=keyboards.choose_tags)
    await state.set_state(Questions.tags)


@user_router.message(Questions.tags)
async def choose_tags(message: Message, state: FSMContext):
    allowed = ['Мероприятие', 'Стипендия', 'Спорт', 'Обучение']
    if message.text in allowed:
        await state.update_data(q2=message.text)
        await message.answer("Сохранено!", reply_markup=ReplyKeyboardRemove())
        await state.clear()

        await state.update_data(q3=message.text)
        await message.answer("Пункт 4. Прикрепите файл:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(Questions.file)
    else:
        await message.answer("Пожалуйста, выберите что-то из предложенного списка:", reply_markup=keyboards.choose_tags)


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
        f"Тэги: {data.get('q3', 'Не указано')} \n"
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

        await state.set_state(UserState.wait_for_choice)
        await message.answer("Новость готова к отправке! Отправить?",
                             reply_markup=keyboards.edit_news)


@user_router.message(UserState.wait_for_choice)
async def edit_news(message: Message, state: FSMContext):
    if message.text == "Редактировать":
        await state.clear()
        await message.answer("Редактируем...", reply_markup=ReplyKeyboardRemove())
        await message.answer("Пункт 1. Название вашей новости:")
        await state.set_state(Questions.topic)
    elif message.text == "Отправить":
        await state.clear()
        await message.answer("Готово! Новость отправлена на валидацию!", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer("Введите ответ с помощью клавиатуры.", reply_markup=keyboards.edit_news)

# @user_router.message()
# async def any_command(message: Message):
#     await message.answer("Неверная команда.")
