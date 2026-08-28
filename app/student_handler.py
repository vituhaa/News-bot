from aiogram import F, Router
import asyncio
from collections import defaultdict
from aiogram.types import Message, ReplyKeyboardRemove, KeyboardButton
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram_media_group import media_group_handler
from aiogram.types import Message, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup

import app.keyboards as keyboards
from app.storage import storage
from app.models import Post

import logging
logger = logging.getLogger(__name__)

user_router = Router()

class Questions(StatesGroup):
    topic = State()
    text = State()
    tags = State()
    files = State()

class UserState(StatesGroup):
    wait_for_choice = State()
    make_another_news = State()
    edit_revision_news = State()


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
    await message.answer("Пункт 1. Название вашей новости (до 200 символов):", reply_markup=keyboards.end)
    await state.set_state(Questions.topic)


@user_router.message(Questions.topic)
async def type_text(message: Message, state: FSMContext):
    if message.text == "Отменить":
        await message.answer("Создание новости отменено. Приходите снова, если захотите создать новость (команда /start)", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    if message.content_type == "text":
        if len(message.text) > 200:
            await message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
            return
        await state.update_data(topic=message.text)
        await message.answer("Пункт 2. Текст вашей новости:", reply_markup=keyboards.end)
        await state.set_state(Questions.text)
    else:
        await message.answer("Неверный ввод! Дайте текстовое название вашей новости.")
        return


@user_router.message(Questions.text)
async def type_tags(message: Message, state: FSMContext):
    if message.text == "Отменить":
        await message.answer("Создание новости отменено. Приходите снова, если захотите создать новость (команда /start)", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    if message.content_type == "text":
        await state.update_data(text=message.text)
        # Получаем категории из БД
        categories = await storage.get_all_categories()
        if not categories:
            await message.answer("Категории ещё не созданы. Обратитесь к администратору.")
            return
        keyboard_buttons = [[KeyboardButton(text=cat)] for cat in categories]
        keyboard_buttons.append([KeyboardButton(text="Отменить")])
        category_keyboard = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Пункт 3. Выберите категорию новости:",
            reply_markup=category_keyboard
        )
        await state.set_state(Questions.tags)
    else:
        await message.answer("Неверный ввод! Дайте текстовое название вашей новости.")
        return


@user_router.message(Questions.tags)
async def choose_tags(message: Message, state: FSMContext):
    if message.text == "Отменить":
        await message.answer("Создание новости отменено. Приходите снова, если захотите создать новость (команда /start)", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    
    categories = await storage.get_all_categories()
    if message.text not in categories:
        keyboard_buttons = [[KeyboardButton(text=cat)] for cat in categories]
        keyboard_buttons.append([KeyboardButton(text="Отменить")])
        keyboard = ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await message.answer(
            "Пожалуйста, выберите категорию из предложенных кнопок:",
            reply_markup=keyboard
        )
        return
    await state.update_data(category=message.text)
    await message.answer(
        "Пункт 4. Прикрепите файл. \n"
        "Можно прикрепить до 10 фото JPG/PNG в одном альбоме или 1 документ формата PDF или DOCX):",
        reply_markup=keyboards.done_keyboard
    )
    await state.set_state(Questions.files)


photo_lock = defaultdict(asyncio.Lock)
tasks = {}

@user_router.message(F.photo,StateFilter(Questions.files))
async def photo_handler(message: Message, state: FSMContext):
    key = (message.chat.id, message.from_user.id)

    async with photo_lock[key]:
        data = await state.get_data()
        photos = data.get("photos", [])

        photos.append({
            "message_id": message.message_id,
            "file_id": message.photo[-1].file_id,
            "media_group_id": message.media_group_id,
        } )
        photos.sort(key=lambda x: x["message_id"])
        await state.update_data(photos=photos)

        old_task = tasks.get(key)
        if old_task and not old_task.done():
            old_task.cancel()

        tasks[key] = asyncio.create_task(finish_photo_batch(message, state, key))


async def finish_photo_batch(message: Message, state:FSMContext, key):
    try:
        await asyncio.sleep(0.5)

        async with photo_lock[key]:
            data = await state.get_data()
            photos = data.get("photos", [])
            if len(photos) > 10:
                photos = photos[:10]
                await state.update_data(photos=photos)
                await message.answer("Нельзя отправлять более 10 фотографий! Остальные прикреплённые фотографии были удалены.",
                                 reply_markup=keyboards.done_keyboard)
            else:
                await message.answer("Фотографии приняты!", reply_markup=keyboards.done_keyboard)

    except asyncio.CancelledError:
        pass
    finally:
        if key in tasks:
            del tasks[key]


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


@user_router.message(F.text.in_({"Готово", "Отменить"}), StateFilter(Questions.files))
async def files_done(message: Message, state: FSMContext):
    if message.text == "Отменить":
        await message.answer("Создание новости отменено. Приходите снова, если захотите создать новость (команда /start)", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    data = await state.get_data()

    photos = data.get("photos", [])
    document = data.get("document")
    if not photos and not document:
        await message.answer("Прикрепите файлы.", reply_markup=keyboards.done_keyboard)
        return
    
    topic = data.get('topic', 'Не указано')
    text = data.get('text', 'Не указано')
    category = data.get('category', 'Не указано')

    result = (
        "Ваша новость:\n"
        f"Название: {topic}\n"
        f"Текст: {text}\n"
        f"Категория: {category}\n"
        f"Фотографии: {len(photos)} шт.\n"
        f"Файл: {document['file_name'] if document else 'Нет'}"
    )

    await message.answer(result)

    if len(photos) == 1:
        await message.answer_photo(photo=photos[0]["file_id"])
    elif len(photos) > 1:
        builder = MediaGroupBuilder()
        for photo_id in photos:
            builder.add_photo(media=photo_id["file_id"])
        
        await message.answer_media_group(
            media=builder.build()
        )

    if document:
        await message.answer_document(document=document["file_id"])
    

    await state.set_state(UserState.wait_for_choice)
    await message.answer(
        "Новость готова к отправке! Отправить?",
        reply_markup=keyboards.edit_news_keyboard
    )


async def notify_admins_about_post(bot, post, is_update: bool = False):
    admins = await storage.get_all_admins()
    action = "Обновлена" if is_update else "Новая"
    for admin in admins:
        try:
            await bot.send_message(
                admin.user_id,
                f"❗️ {action} новость от @{post.username or 'пользователь'} (ID: {post.user_id}):\n"
                f"Заголовок: {post.topic}\n"
                f"Для обработки нажмите /review {post.id}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin.user_id}: {e}")


@user_router.message(UserState.wait_for_choice)
async def edit_or_submit(message: Message, state: FSMContext):
    if message.text == "Отменить":
        await message.answer("Создание новости отменено. Приходите снова, если захотите создать новость (команда /start)", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        return
    
    elif message.text == "Редактировать":
        data = await state.get_data()
        await state.clear()

        await state.update_data(
            topic=data.get("topic"),
            text=data.get("text"),
            category=data.get("category"),
            photos=[],
            document=None
        )
        
        await message.answer("Редактируем... Начните с названия.", reply_markup=ReplyKeyboardRemove())
        await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
        await state.set_state(Questions.topic)

    elif message.text == "Отправить":
        data = await state.get_data()
        photos = data.get("photos", [])
        document = data.get("document")

        topic = data.get('topic')
        text = data.get('text')
        category = data.get('category')
        edit_post_id = data.get('edit_post_id')

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
            media_names.append(document.get("file_name", "document"))

        if not all([topic, text, category]):
            await message.answer("Ошибка: не все данные заполнены. Начните заново /start")
            await state.clear()
            return

        if not media_ids:
            await message.answer("Ошибка: необходимо прикрепить хотя бы одно медиа-вложение.")
            return

        if edit_post_id:
            post = await storage.get_post(edit_post_id)
            if not post:
                await message.answer("Ошибка: пост для редактирования не найден. Попробуйте заново /start")
                await state.clear()
                return

            success = await storage.update_post(
                edit_post_id,
                topic=topic,
                text=text,
                category=category,
                media_ids=media_ids,
                media_types=media_types,
                media_names=media_names,
                status='pending',
                taken_by=None,             
                taken_at=None,
                moderated_by=None,
                moderated_at=None,
                comment=None
            )
            if not success:
                await message.answer("Ошибка при обновлении поста. Попробуйте заново.")
                await state.clear()
                return

            saved_post = await storage.get_post(edit_post_id)
            if not saved_post:
                await message.answer("Ошибка: не удалось получить обновлённый пост.")
                await state.clear()
                return

            await state.update_data(edit_post_id=None)
            await notify_admins_about_post(message.bot, saved_post, is_update=True)

            await state.set_state(UserState.make_another_news)
            await message.answer(
                f"✅ Новость #{saved_post.id} обновлена и отправлена на модерацию.\nХотите создать ещё одну?",
                reply_markup=keyboards.make_another_news_keyboard
            )

        else:
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
            saved_post = await storage.create_post(post)
            await notify_admins_about_post(message.bot, saved_post, is_update=False)

            await state.set_state(UserState.make_another_news)
            await message.answer(
                f"Готово! Новость отправлена на валидацию (ID #{saved_post.id}).\nХотите создать ещё одну?",
                reply_markup=keyboards.make_another_news_keyboard
            )

    else:
        await message.answer(
            "Используйте кнопки клавиатуры.",
            reply_markup=keyboards.edit_news_keyboard
        )


@user_router.message(UserState.make_another_news)
async def make_another_news_func(message: Message, state: FSMContext):
    if message.text == "Да":
        await message.answer("Создаём ещё одну новость...")
        await state.clear()
        await start_command(message, state)
    elif message.text == "Нет":
        await state.clear()
        await message.answer(
            "Все новости отправлены. Приходите снова, если захотить создать новость (команда /start).",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "Используйте кнопки клавиатуры.",
            reply_markup=keyboards.make_another_news_keyboard
        )


@user_router.message(UserState.edit_revision_news)
async def edit_news(message: Message, state: FSMContext):
    if message.text == "Изменить новость":
        data = await state.get_data()

        post_id = data.get('pending_edit_post_id')
        post_topic = data.get('pending_edit_topic')
        post_text = data.get('pending_edit_text')
        post_files = data.get('pending_edit_files', [])
        moderator_comment = data.get('pending_edit_comment')

        await state.update_data(
            edit_post_id=post_id,
            edit_topic=post_topic,
            edit_text=post_text,
            edit_files=post_files,
            edit_comment=moderator_comment
        )
        await message.answer(
            f"Редактирование новости #{post_id}\n\n"
            f"Комментарий модератора: {moderator_comment}\n"
            f"Текущее название: {post_topic}\n\n"
            f"Введите новое название (до 200 символов):",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(Questions.topic)
    else:
        await message.answer(
            "Используйте кнопки клавиатуры.",
            reply_markup=keyboards.edit_revision_button
        )