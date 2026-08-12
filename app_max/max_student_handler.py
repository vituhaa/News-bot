#from aiogram import F, Router
#from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
#from aiogram.filters import Command, StateFilter
#from aiogram.fsm.state import State, StatesGroup
#from aiogram.fsm.context import FSMContext
#from aiogram.utils.media_group import MediaGroupBuilder
#from aiogram_media_group import media_group_handler

from maxapi import F, Router
from maxapi.types import MessageCreated, CallbackQueryCreated
from maxapi.filters.command import CommandStart, Command
from maxapi.fsm import State, StatesGroup, FSMContext
#from maxapi.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
from app_max.max_keyboards import (  # импортируем клавиатуры
    get_category_keyboard,
    get_done_keyboard,
    get_edit_submit_keyboard,
    CATEGORIES
)

import app.keyboards as keyboards
from app.storage import storage
from app.models import Post

user_router = Router()

class Questions(StatesGroup):
    topic = State()
    text = State()
    tags = State()
    files = State()

class UserState(StatesGroup):
    wait_for_choice = State()

def check_input_type(message) -> tuple[bool, str]:
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


@user_router.message_created(CommandStart()) #немного другой фильтр
async def start_command(event: MessageCreated, state: FSMContext):
    await state.clear()
    await event.essage.answer(
        "Здравствуйте! Я - новостной бот.\n"
        "Для создания новости заполните форму:",
        #reply_markup=ReplyKeyboardRemove() в макс нет данного вида клавиатур. Есть только те что скрываются автоматически, значит данное действие больше не требуется
    )
    await event.answer("Пункт 1. Название вашей новости (до 200 символов):")
    await state.set_state(Questions.topic)

@user_router.message_created(Questions.topic, F.message.body.text) # сразу проверяем на наличие текста
async def type_text(event: MessageCreated, state: FSMContext):
    text = event.message.body.text
    if len(text) > 200:
        await event.message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
        return
    await state.update_data(topic=text)
    await event.message.answer("Пункт 2. Текст вашей новости:")
    await state.set_state(Questions.text)
# await message.answer("Неверный ввод! Дайте текстовое название вашей новости.") просто не выполнится этот вариант тк просто до него
#  не дойдём. Хендлер просто не будет вызван - проигнорируется.
# Для этого ставим ловушку для всего, что не текст (шаг topic)
@user_router.message_created(Questions.topic)
async def type_text_invalid(event: MessageCreated, state: FSMContext):
    await event.message.answer(
        "Неверный ввод! Пожалуйста, отправьте текстовое название новости."
    )

@user_router.message_created(Questions.text, F.message.body.text)
async def type_tags(event: MessageCreated, state: FSMContext):
    await state.update_data(text=event.message.body.text)
    await event.message.answer(
        "Пункт 3. Выберите категорию новости:",
        reply_markup=get_category_keyboard()  # используем функцию
        #reply_markup=keyboards.category_keyboard
    )
    await state.set_state(Questions.tags)
    
@user_router.message_created(Questions.text)
async def type_tags_invalid(event: MessageCreated, state: FSMContext):
    await event.message.answer(
        "Неверный ввод! Пожалуйста, отправьте текстовое содержание новости."
    )

@user_router.callback_query_created(Questions.tags)
async def choose_tags(callback: CallbackQueryCreated, state: FSMContext):
    if not callback.data.startswith("cat_"):
        await callback.answer("Пожалуйста, выберите категорию из предложенных кнопок.")
        return
    category = callback.data.replace("cat_", "")
    if category not in CATEGORIES:
        await callback.answer("Неизвестная категория.")
        return
    await state.update_data(category=category)
    await callback.message.edit_text(f"Выбрана категория: {category}")
    await callback.answer()

# немного иная логика для макса нужна
    await callback.message.answer(
        "Пункт 4. Прикрепите файлы.\n"
        "Можно прикрепить до 10 фото JPG/PNG или один документ PDF/DOCX.\n"
        "После загрузки всех файлов нажмите кнопку 'Готово'."
    )
    await callback.message.answer(
        "Нажмите кнопку, когда закончите загрузку файлов.",
        reply_markup=get_done_keyboard()
    )
    await state.set_state(Questions.files)

@user_router.message_created(Questions.tags)
async def choose_tags_invalid(event: MessageCreated, state: FSMContext):
    await event.message.answer(
        "Пожалуйста, выберите категорию, нажав на кнопку ниже.",
        reply_markup=get_category_keyboard()
    )

""""""
@user_router.message_created(Questions.files, F.message.body.photo)
async def photo_handler(event: MessageCreated, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 10:
        await event.message.answer("Нельзя отправлять более 10 фотографий!")
        return
    file_id = event.message.body.photo[-1].file_id
    photos.append(file_id)
    await state.update_data(photos=photos)
    await event.message.answer(f"Фотография принята ({len(photos)}/10). Продолжайте или нажмите 'Готово'.")

@user_router.message_created(Questions.files, F.message.body.document)
async def document_handler(event: MessageCreated, state: FSMContext):
    data = await state.get_data()
    if data.get("document"):
        await event.message.answer("Можно прикрепить только один документ. Файл не добавлен.")
        return
    is_allowed, output = check_input_type(event.message)
    if not is_allowed:
        await event.message.answer(output)
        return
    doc = event.message.body.document
    await state.update_data(document={
        "file_id": doc.file_id,
        "file_name": doc.file_name,
        "file_type": doc.mime_type
    })
    await event.message.answer(f"Документ '{doc.file_name}' принят. Нажмите 'Готово', когда закончите.")

@user_router.message_created(Questions.files)
async def files_invalid(event: MessageCreated, state: FSMContext):
    await event.message.answer(
        "Пожалуйста, прикрепите файл (фото или документ) или нажмите кнопку 'Готово'."
    )

# Обработчик кнопки "Готово"
@user_router.callback_query_created(Questions.files, F.data == "files_done")
async def files_done(callback: CallbackQueryCreated, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    document = data.get("document")
    if not photos and not document:
        await callback.answer("Вы не прикрепили ни одного файла! Сначала загрузите файлы.", show_alert=True)
        return

    topic = data.get('topic', 'Не указано')
    text = data.get('text', 'Не указано')
    category = data.get('category', 'Не указано')

    result = (
        "Ваша новость:\n"
        f"Название: {topic}\n"
        f"Текст: {text}\n"
        f"Категория: {category}\n"
        f"Фотографий: {len(photos)}\n"
        f"Документ: {document['file_name'] if document else 'Нет'}"
    )

    await callback.message.answer(result)

    if photos:
        await callback.message.answer_photo(photo=photos[0])
    elif document:
        await callback.message.answer_document(document=document["file_id"])

    await callback.message.answer(
        "Новость готова к отправке! Выберите действие:",
        reply_markup=get_edit_submit_keyboard()
    )
    await state.set_state(UserState.wait_for_choice)
    await callback.answer()


@user_router.callback_query_created(UserState.wait_for_choice)
async def edit_or_submit(callback: CallbackQueryCreated, state: FSMContext):
    if callback.data == "edit_news":
        data = await state.get_data()
        await state.clear()
        await state.update_data(data)
        await callback.message.answer("Редактируем... Начните с названия.")
        await callback.message.answer("Пункт 1. Название вашей новости (до 200 символов):")
        await state.set_state(Questions.topic)
        await callback.answer()
        return

    elif callback.data == "submit_news":
        data = await state.get_data()
        photos = data.get("photos", [])
        document = data.get("document")
        topic = data.get('topic')
        text = data.get('text')
        category = data.get('category')

        media_ids = []
        media_types = []
        media_names = []
        for photo_id in photos:
            media_ids.append(photo_id)
            media_types.append("photo")
            media_names.append(None)
        if document:
            media_ids.append(document["file_id"])
            media_types.append("document")
            media_names.append(document["file_name"])

        if not all([topic, text, category]) or not media_ids:
            await callback.message.answer("Ошибка: не все данные заполнены. Начните заново /start")
            await state.clear()
            await callback.answer()
            return

        post = Post(
            user_id=callback.from_user.id,
            username=callback.from_user.username or f"id_{callback.from_user.id}",
            topic=topic,
            text=text,
            category=category,
            media_ids=media_ids,
            media_types=media_types,
            media_names=media_names
        )
        saved_post = storage.create_post(post)
        await state.clear()
        await callback.message.answer(
            f"Готово! Новость отправлена на валидацию (ID #{saved_post.id}).\n"
            "Ожидайте решения администратора."
        )
        await callback.answer()
        return

    await callback.answer("Неизвестная команда.")


@user_router.message_created(Command("id"))
async def get_id(event: MessageCreated):
    await event.message.answer(f"Ваш ID: {event.from_user.id}")


@user_router.message_created()
async def any_command(event: MessageCreated):
    await event.message.answer("Неизвестная команда. Следуйте инструкциям, описанным в сообщениях бота.")