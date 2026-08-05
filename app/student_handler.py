from aiogram import F, Router
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import app.keyboards as keyboards
from app.storage import storage
from app.models import Post

user_router = Router()
import logging
logger = logging.getLogger(__name__)

class CreateNews(StatesGroup):
    topic = State()
    text = State()
    tags = State()
    file = State()

class UserActions(StatesGroup):
    wait_for_choice = State() # ожидание выбора отправить/редактировать

def check_file_type(message: Message) -> tuple[bool, str]:
    """Проверка типа файла"""
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
    return False, "Пожалуйста, прикрепите фото или документ."

# Уведомляет всех администраторов о новой новости
async def notify_admins_about_new_post(post: Post):
    admins = storage.get_all_admins()
    
    if not admins:
        logger.warning("Нет администраторов для уведомления")
        return
    
    from aiogram import Bot
    from app.config import BOT_TOKEN
    
    bot = Bot(token=BOT_TOKEN)
    
    text = (
        "НОВАЯ НОВОСТЬ\n"
        "=" * 30 + "\n"
        f"Автор: @{post.username}\n"
        f"Заголовок: {post.topic}\n"
        f"Категория: {post.category or 'Без категории'}\n"
        f"ID: #{post.id}\n\n"
        "Для обработки используйте /admin"
    )
    
    for admin in admins:
        try:
            await bot.send_message(
                chat_id=admin.user_id,
                text=text
            )
            logger.info(f"Уведомление отправлено админу {admin.user_id}")
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin.user_id}: {e}")
    
    await bot.session.close()

@user_router.message(Command("start"))
async def start_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Здравствуйте! Я - новостной бот. \n" \
                         "Для создания новости заполните форму:", reply_markup=ReplyKeyboardRemove())
    await message.answer("Пункт 1. Название вашей новости (до 200 символов):")
    await state.set_state(CreateNews.topic)

@user_router.message(CreateNews.topic)
async def process_topic(message: Message, state: FSMContext):
    await state.update_data(q1=message.text)
    if (len(message.text) < 200):
        await message.answer("Пункт 2. Текст вашей новости:")
    else:
        await message.answer("Слишком длинный текст, максимальная длина - 200 символов. Попробуйте снова.")
        return
    await state.set_state(CreateNews.text)   

@user_router.message(CreateNews.text)
async def process_text(message: Message, state: FSMContext):
    await message.answer(
        "Пункт 3. Тэг вашей новости:",
        reply_markup=keyboards.choose_tags
    )
    await state.set_state(CreateNews.tags)

@user_router.message(CreateNews.tags)
async def process_tags(message: Message, state: FSMContext):
    allowed = ['Мероприятие', 'Стипендия', 'Спорт', 'Обучение']
    
    if message.text in allowed:
        await state.update_data(category=message.text)
        await message.answer(
            "Сохранено!",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer(
            "Пункт 4. Прикрепите файл:",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.set_state(CreateNews.file)
    else:
        await message.answer("Пожалуйста, выберите что-то из предложенного списка:", reply_markup=keyboards.choose_tags)

@user_router.message(StateFilter(CreateNews.file), F.document | F.photo)
async def process_file(message: Message, state: FSMContext):
    file_id = None
    file_name = None
    file_type = None
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        file_type = 'document'
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "Фото"
        file_type = 'photo'

    # Проверяем тип файла
    is_allowed, output = check_file_type(message)
    if not is_allowed:
        await message.answer(output)
        return
    
    await state.update_data(
        file_id=file_id,
        file_name=file_name,
        file_type=file_type
    )

    data = await state.get_data()

    result = (
        "Ваша новость:\n"
        f"Название: {data.get('topic', 'Не указано')}\n"
        f"Текст: {data.get('text', 'Не указано')}\n"
        f"Тэги: {data.get('category', 'Не указано')}\n"
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

    await state.set_state(UserActions.wait_for_choice)
    await message.answer(
        "Новость готова к отправке! Отправить?",
        reply_markup=keyboards.edit_news
    )

@user_router.message(StateFilter(CreateNews.file))
async def wrong_file(message: Message):
    await message.answer(
        "Неверный ввод! Прикрепите файл."
    )

@user_router.message(UserActions.wait_for_choice)
async def handle_choice(message: Message, state: FSMContext):
    if message.text == "Редактировать":
        await state.clear()
        await message.answer(
            "Редактируем...",
            reply_markup=ReplyKeyboardRemove()
        )
        await message.answer("Пункт 1. Название вашей новости:")
        await state.set_state(CreateNews.topic)
        
    elif message.text == "Отправить":
        data = await state.get_data()
        
        # Создаём пост в хранилище
        post = Post(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name,
            topic=data.get('topic'),
            text=data.get('text'),
            category=data.get('category'),
            media_ids=[data.get('file_id')] if data.get('file_id') else [],
            media_types=[data.get('file_type')] if data.get('file_type') else [],
            media_names=[data.get('file_name')] if data.get('file_name') else []
        )
        post.status = 'pending'
        storage.create_post(post)
        
        logger.info(f"Новый пост #{post.id} от @{post.username}: {post.topic}")
        
        await state.clear()
        await message.answer(
            "Готово! Новость отправлена на валидацию! Хотите создать ещё одну?",
            reply_markup=keyboards.make_another_news
        )
        
        # Уведомляем администраторов
        await notify_admins_about_new_post(post)
        
    else:
        await message.answer(
            "Введите ответ с помощью клавиатуры.",
            reply_markup=keyboards.edit_news
        )

@user_router.message(F.text.in_(["Да", "Нет"]))
async def handle_another_news(message: Message, state: FSMContext):
    if message.text == "Да":
        await message.answer(
            "Отлично! Давайте создадим ещё одну новость.",
            reply_markup=ReplyKeyboardRemove()
        )
        await start_command(message, state)
    else:
        await message.answer(
            "Спасибо! Ваша новость отправлена на проверку.",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()

@user_router.message()
async def any_command(message: Message):
    await message.answer(
        "Неверная команда. Используйте /start для создания новости."
    )