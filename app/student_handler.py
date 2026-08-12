from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove, CallbackQuery
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram_media_group import media_group_handler

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
    await message.answer(
        "Здравствуйте! Я - новостной бот.\n"
        "Для создания новости заполните форму:",
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
    await state.set_state(Questions.topic)


@user_router.message(Questions.topic)
async def type_text(message: Message, state: FSMContext):
    if message.content_type == "text":
        if len(message.text) > 200:
            await message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
            return
        await state.update_data(topic=message.text)
        await message.answer("Пункт 2. Текст вашей новости:")
        await state.set_state(Questions.text)
    else:
        await message.answer("Неверный ввод! Дайте текстовое название вашей новости.")
        return


@user_router.message(Questions.text)
async def type_tags(message: Message, state: FSMContext):
    if message.content_type == "text":
        await state.update_data(text=message.text)
        await message.answer(
            "Пункт 3. Выберите категорию новости:",
            reply_markup=keyboards.category_keyboard
        )
        await state.set_state(Questions.tags)
    else:
        await message.answer("Неверный ввод! Дайте текстовое название вашей новости.")
        return


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
        "Пункт 4. Прикрепите файл. \n"
        "Можно прикрепить до 10 фото JPG/PNG в одном альбоме или 1 документ формата PDF или DOCX):",
        reply_markup=keyboards.done_keyboard
    )
    await state.set_state(Questions.files)


@user_router.message(F.photo, ~F.media_group_id, StateFilter(Questions.files))
async def single_photo_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    photos = data.get("photos", [])
    if len(photos) >= 10:
        await message.answer("Нельзя отправлять более 10 фотографий!", reply_markup=keyboards.done_keyboard)
        return

    photos.append(message.photo[-1].file_id)

    await state.update_data(photos=photos)
    await message.answer("Фотографии приняты!", reply_markup=keyboards.done_keyboard)


@user_router.message(F.photo, F.media_group_id, StateFilter(Questions.files))
@media_group_handler
async def album_handler(messages: list[Message], state: FSMContext):
    photos = [x.photo[-1].file_id for x in messages if x.photo]
    data = await state.get_data()
    received = data.get("photos", [])
    diff = 10 - len(received)

    if diff <= 0:
        await messages[0].answer("Нельзя отправлять более 10 фотографий! Остальные прикреплённые фотографии были удалены.",
                                 reply_markup=keyboards.done_keyboard)
        return
    
    accepted_photos = photos[:diff]

    await state.update_data(
        photos=received + accepted_photos
    )

    if len(photos) > diff:
        await messages[0].answer("Нельзя отправлять более 10 фотографий! Остальные прикреплённые фотографии были удалены.",
                                 reply_markup=keyboards.done_keyboard)
    
    await messages[0].answer("Фотографии приняты!", reply_markup=keyboards.done_keyboard)


@user_router.message(F.document, ~F.media_group_id, StateFilter(Questions.files))
async def single_file_handler(message: Message, state: FSMContext):
    data = await state.get_data()

    if data.get("document"):
        await message.answer("Можно прикрепить только один документ формата PDF или DOCX.", reply_markup=keyboards.done_keyboard)
        return

    is_allowed, output = check_input_type(message)
    if not is_allowed:
        await message.answer(output)
        return

    document = {
        "file_id": message.document.file_id,
        "file_name": message.document.file_name,
        "file_type": message.document.mime_type
        }

    await state.update_data(document=document)

    await message.answer("Документ принят!", reply_markup=keyboards.done_keyboard)


@user_router.message(F.document, F.media_group_id, StateFilter(Questions.files))
@media_group_handler
async def files_album_handler(messages: list[Message], state: FSMContext):
    await messages[0].answer("Можно прикрепить только один документ формата PDF или DOCX.", reply_markup=keyboards.done_keyboard)


@user_router.message(F.text == "Готово", StateFilter(Questions.files))
async def files_done(message: Message, state: FSMContext):
    data = await state.get_data()

    photos = data.get("photos", [])
    document = data.get("document")
    if not photos and not document:
        await message.answer("Прикрепите файлы.", reply_markup=keyboards.done_keyboard)
        return
    
    topic = data.get('topic', 'Не указано')
    text = data.get('text', 'Не указано')
    category = data.get('category', 'Не указано')

    # карточка для предпросмотра
    result = (
        "Ваша новость:\n"
        f"Название: {topic}\n"
        f"Текст: {text}\n"
        f"Категория: {category}\n"
        f"Фотографии: {len(photos)} шт.\n"
        f"Файл: {document['file_name'] if document else 'Нет'}"
    )

    await message.answer(result)

    # предпросмотр фотографий:
    if len(photos) == 1:
        await message.answer_photo(photo=photos[0])
    elif len(photos) > 1:
        builder = MediaGroupBuilder()
        for photo_id in photos:
            builder.add_photo(media=photo_id)
        
        await message.answer_media_group(
            media=builder.build()
        )

    # предпросмотр документа:
    if document:
        await message.answer_document(document=document["file_id"])
    

    await state.set_state(UserState.wait_for_choice)
    await message.answer(
        "Новость готова к отправке! Отправить?",
        reply_markup=keyboards.edit_news_keyboard
    )


@user_router.message(UserState.wait_for_choice)
async def edit_or_submit(message: Message, state: FSMContext):
    if message.text == "Редактировать":

        # возвращаемся к первому шагу с сохранёнными данными
        data = await state.get_data()
        await state.clear()

        # сохраняем старые данные в контекст, чтобы при повторном заполнении они не пропали
        await state.update_data(data)
        await message.answer("Редактируем... Начните с названия.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
        await state.set_state(Questions.topic)

    elif message.text == "Отправить":
        # Получаем данные
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
            media_ids.append(document["file_type"])
            media_ids.append(document["file_name"])

        if not all([topic, text, category]):
            await message.answer("Ошибка: не все данные заполнены. Начните заново /start")
            await state.clear()
            return
        
        if not media_ids:
            await message.answer("Ошибка: необходимо прикрепить хотя бы одно медиа-вложение.")
            return

        # Создаём объект Post
        post = Post(
            user_id=message.from_user.id,
            username=message.from_user.username or f"id_{message.from_user.id}",
            topic=topic,
            text=text,
            category=category,
            media_ids=media_ids,
            media_types=media_types,
            media_names=media_names,
            status="pending"
        )
        # Сохраняем в хранилище
        saved_post = storage.create_post(post)

        await state.clear()
        await message.answer(
            f"Готово! Новость отправлена на валидацию (ID #{saved_post.id}).",
            reply_markup=ReplyKeyboardRemove()
        )

    else:
        await message.answer(
            "Используйте кнопки клавиатуры.",
            reply_markup=keyboards.edit_news_keyboard
        )


# @user_router.message()
# async def any_command(message: Message):
#     await message.answer("Неизвестная команда. Следуйте инструкциям, описанным в сообщениях бота.")