from aiogram import F, Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime

import app.keyboards as keyboards
from app.storage import storage
from app.models import Post

user_router = Router()

# ===== Состояния студента =====
class Questions(StatesGroup):
    topic = State()
    text = State()
    tags = State()
    file = State()

class UserState(StatesGroup):
    wait_for_choice = State()


# Вспомогательная функция проверки типа файла
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


# ===== Обработчики =====

@user_router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "Здравствуйте! Я - новостной бот.\n"
        "Для создания новости заполните форму:",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
    await state.set_state(Questions.topic)


@user_router.message(Questions.topic)
async def type_text(message: Message, state: FSMContext):
    if len(message.text) > 200:
        await message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
        return
    await state.update_data(topic=message.text)
    await message.answer("Пункт 2. Текст вашей новости:")
    await state.set_state(Questions.text)


@user_router.message(Questions.text)
async def type_tags(message: Message, state: FSMContext):
    await state.update_data(text=message.text)
    await message.answer(
        "Пункт 3. Выберите категорию новости:",
        reply_markup=keyboards.category_keyboard
    )
    await state.set_state(Questions.tags)


@user_router.message(Questions.tags)
async def choose_tags(message: Message, state: FSMContext):
    allowed = ['Мероприятие', 'Стипендия', 'Спорт', 'Обучение']
    if message.text not in allowed:
        await message.answer(
            "Пожалуйста, выберите категорию из предложенных кнопок:",
            reply_markup=keyboards.category_keyboard
        )
        return
    await state.update_data(category=message.text)
    await message.answer(
        "Пункт 4. Прикрепите файл (фото JPG/PNG или документ PDF/DOCX):",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Questions.file)


@user_router.message(StateFilter(Questions.file), F.document | F.photo)
async def file_handler(message: Message, state: FSMContext):
    # Проверяем допустимость файла
    is_allowed, error_msg = check_input_type(message)
    if not is_allowed:
        await message.answer(error_msg)
        return

    # Сохраняем информацию о файле
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "Документ"
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "Фото"
        file_type = "photo"
    else:
        return

    await state.update_data(
        file_id=file_id,
        file_name=file_name,
        file_type=file_type
    )

    # Получаем все данные
    data = await state.get_data()
    topic = data.get('topic', 'Не указано')
    text = data.get('text', 'Не указано')
    category = data.get('category', 'Не указано')

    # Формируем карточку для предпросмотра
    result = (
        "Ваша новость:\n"
        f"Название: {topic}\n"
        f"Текст: {text}\n"
        f"Категория: {category}\n"
        f"Файл: {file_name}"
    )

    # Отправляем предпросмотр с файлом
    if file_type == "document":
        await message.answer_document(
            document=file_id,
            caption=result
        )
    else:  # photo
        await message.answer_photo(
            photo=file_id,
            caption=result
        )

    # Переходим к выбору действия
    await state.set_state(UserState.wait_for_choice)
    await message.answer(
        "Новость готова к отправке! Отправить?",
        reply_markup=keyboards.edit_news_keyboard
    )


@user_router.message(UserState.wait_for_choice)
async def edit_or_submit(message: Message, state: FSMContext):
    if message.text == "Редактировать":
        # Возвращаем к первому шагу с сохранёнными данными
        data = await state.get_data()
        await state.clear()
        # Сохраняем старые данные в контекст, чтобы при повторном заполнении они не пропали
        await state.update_data(data)
        await message.answer("Редактируем... Начните с названия.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
        await state.set_state(Questions.topic)

    elif message.text == "Отправить":
        # Получаем данные
        data = await state.get_data()
        topic = data.get('topic')
        text = data.get('text')
        category = data.get('category')
        file_id = data.get('file_id')
        file_name = data.get('file_name')
        file_type = data.get('file_type')

        if not all([topic, text, category, file_id]):
            await message.answer("Ошибка: не все данные заполнены. Начните заново /start")
            await state.clear()
            return

        # Создаём объект Post
        post = Post(
            user_id=message.from_user.id,
            username=message.from_user.username or f"id_{message.from_user.id}",
            topic=topic,
            text=text,
            category=category,
            media_ids=[file_id],
            media_types=[file_type],
            media_names=[file_name]
        )
        # Сохраняем в хранилище
        saved_post = storage.create_post(post)

        # Очищаем состояние
        await state.clear()
        await message.answer(
            f"Готово! Новость отправлена на валидацию (ID #{saved_post.id}).",
            reply_markup=ReplyKeyboardRemove()
        )

        # TODO: уведомить администраторов (можно реализовать позже)

    else:
        await message.answer(
            "Используйте кнопки клавиатуры.",
            reply_markup=keyboards.edit_news_keyboard
        )


# Обработчик всех остальных сообщений
@user_router.message()
async def any_command(message: Message):
    await message.answer("Неверная команда. Используйте /start для создания новости.")