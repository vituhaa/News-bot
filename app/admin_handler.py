from aiogram import Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, BufferedInputFile, InputMediaPhoto
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot
from datetime import datetime
import logging
import json
import zipfile
import io
import os
import re
from dotenv import load_dotenv

from app.storage import storage
from app.models import Post, Admin
from app.student_handler import UserState
import app.keyboards as keyboards

# Глобальная переменная для хранения диспетчера
_dispatcher = None

def set_dispatcher(dp):
    """Устанавливает диспетчер для использования в админ-роутере."""
    global _dispatcher
    _dispatcher = dp


load_dotenv()

admin_router = Router()
logger = logging.getLogger(__name__)

ADMINS = os.getenv("ADMINS", "")
admins_list = [int(x.strip()) for x in ADMINS.split(",") if x.strip()]

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)
admin_page = {}

class AdminState(StatesGroup):
    wait_for_choice = State()
    delete_admin = State()
    wait_for_comment = State()
    wait_for_reject_comment = State()
    wait_for_channel = State()
    wait_for_user_id = State()

# =========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===========
def is_admin(user_id: int) -> bool:
    return user_id in admins_list

def init_admins(admins_ids):
    for admin_id in admins_ids:
        print(admin_id)
        if not storage.get_admin(admin_id):
            admin = Admin(
                user_id=admin_id,
                username=f"superadmin_{admin_id}",
                role='superadmin',
                added_by=admin_id
            )
            storage.add_admin(admin)

def format_post_text(post: Post) -> str:
    status_names = {
        'draft': 'Черновик',
        'pending': 'На модерации',
        'revision': 'Требуется доработка',
        'approved': 'Одобрено',
        'published': 'Опубликовано',
        'rejected': 'Отклонено'
    }

    text = f"Новость #{post.id}\n"
    text += f"Автор: @{post.username or 'Неизвестно'}\n"
    text += f"Статус: {status_names.get(post.status, post.status)}\n"
    if post.category:
        text += f"Категория: {post.category}\n"
    text += f"Создано: {post.created_at.strftime('%d.%m.%Y %H:%M')}\n"
    if post.taken_by:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        text += f"Взял на модерацию: {admin_name}\n"
    text += f"\nЗАГОЛОВОК:\n{post.topic}\n"
    text += f"\nТЕКСТ:\n{post.text}\n"
    if post.media_ids:
        text += f"\nВЛОЖЕНИЯ: {len(post.media_ids)} шт.\n"
    if post.comment:
        text += f"\nКОММЕНТАРИЙ:\n{post.comment}\n"
    return text

# =========== АДМИН ===========
@admin_router.message(Command("admin"))
async def start_admin(message: Message):
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("У вас нет прав администратора.")
        return
    
    await show_admin_panel(message, user_id)


async def show_admin_panel(message: Message, user_id: int):
    pending_posts = storage.get_pending_count()

    text = f"Панель администратора\n\n"
    text += f"Новостей в очереди: {pending_posts}\n"
    text += f"Всего администраторов: {len(storage.get_all_admins())}\n"

    channel_info = storage.get_channel_info()
    if channel_info['is_configured']:
        channel_display = channel_info.get('channel_username') or channel_info.get('channel_link')
        text += f"Канал: {channel_display}\n"
    else:
        text += "Канал не настроен\n"

    await message.answer("Подключаем клавиатуру администратора...", reply_markup=ReplyKeyboardRemove())
    keyboard = keyboards.get_admin_main_keyboard(pending_posts)
    await message.answer(text, reply_markup=keyboard)


# так как администраторы должны иметь возможность перейти к заявке по ID:
@admin_router.message(Command("review"))
async def review_post_by_id(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("У вас нет прав администратора.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Укажите ID новости, например: /review 123")
        return

    try:
        post_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return

    post = storage.get_post(post_id)
    if not post:
        await message.answer(f"Новость с ID {post_id} не найдена.")
        return

    await show_post_to_admin(message, post, show_next=False)


@admin_router.callback_query(lambda c: c.data == "admin_inbox")
async def admin_inbox(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    pending_posts = storage.get_pending_posts()
    if not pending_posts:
        await callback.message.edit_text("Нет постов на модерацию.")
        await callback.answer()
        return

    post = pending_posts[0]
    await show_post_to_admin(callback.message, post)
    await callback.answer()


@admin_router.callback_query(lambda c: c.data == "admin_next")
async def admin_next(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    pending_posts = storage.get_pending_posts()
    if not pending_posts:
        await callback.message.edit_text("Все новости обработаны!")
        await callback.answer()
        return

    page = admin_page.get(user_id, 0)
    if page >= len(pending_posts):
        page = 0

    post = pending_posts[page]
    admin_page[user_id] = page + 1
    show_next = (page + 1) < len(pending_posts)
    await show_post_to_admin(callback.message, post, progress=f"({page + 1} / {len(pending_posts)})", show_next=show_next)
    await callback.answer()


async def show_post_to_admin(message: Message, post: Post, progress: str = "", show_next: bool = True):
    text = format_post_text(post)
    if progress:
        text = f"{progress}\n {text}"
    keyboard = keyboards.get_admin_post_keyboard(post.id, show_next=show_next)

    photos = []
    documents = []

    for i, media_id in enumerate(post.media_ids):
        if i < len(post.media_types):
            media_type = post.media_types[i]
        else:
            media_type = 'unknown'
        
        if media_type == 'photo':
            photos.append(media_id)
        elif media_type == 'document':
            documents.append(media_id)
        else:
            documents.append(media_id)

    if photos:
        if len(photos) == 1:
            await message.answer_photo(
                photo=photos[0],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
        else:
            await message.answer_photo(
                photo=photos[0],
                caption=text,
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            if len(photos) > 1:
                album = []
                for photo_id in photos[1:]:
                    album.append(InputMediaPhoto(media=photo_id))
                
                await message.answer_media_group(media=album)


    if documents:
        for i, doc_id in enumerate(documents):
            caption = text if not photos and i == 0 else None
            reply_markup = keyboard if not photos and i == 0 else None
            
            await message.answer_document(
                document=doc_id,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode='HTML' if caption else None
            )


@admin_router.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_post(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    post_id = int(callback.data.split('_')[1])
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return

    if post.taken_by and post.taken_by != user_id:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        await callback.answer(f"Пост уже взял {admin_name}", show_alert=True)
        return

    if not post.taken_by:
        storage.update_post(post_id, taken_by=user_id, taken_at=datetime.now())

    channel_info = storage.get_channel_info()
    conf_info = channel_info["is_configured"]

    if conf_info:
        text = f"Новость #{post_id} опубликована в канале!\nАвтор: @{post.username}"

        if callback.message.photo or callback.message.document:
            await callback.message.edit_caption(
                caption=text,
                reply_markup=None
            )
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=None
            )

        chat_id = channel_info.get("channel_link") or channel_info.get("channel_username")
        value = chat_id.strip()
        if 't.me' in value or 'telegram.me' in value:
            match = re.search(r't\.me/([a-zA-Z0-9_]+)', value)
            if match:
                username = match.group(1)
                username_with_at = f"@{username}"
            else:
                await callback.answer(
                    "Не удалось распознать ссылку на канал. "
                    "Используйте формат: https://t.me/newsbottest100",
                    show_alert=True
                )
                return
        elif value.startswith('@'):
            username_with_at = value
            username = value[1:]
        else:
            username = value
            username_with_at = f"@{value}"

        try:
            chat = await bot.get_chat(username_with_at)
            chat_id = chat.id
            storage.set_setting('channel_id', chat.id)
            
            await callback.answer(
                f"Канал успешно подключен: {chat.title}",
                show_alert=True
            )
            
        except Exception as e:
            try:
                chat = await bot.get_chat(username)
                chat_id = chat.id
                storage.set_setting('channel_id', chat.id)
                
                await callback.answer(
                    f"Канал успешно подключен: {chat.title}",
                    show_alert=True
                )
                
            except Exception as e2:            
                await callback.answer(
                    "Не удалось найти канал. Проверьте:\n"
                    "1. Правильность ссылки\n"
                    "2. Бот является администратором\n"
                    "3. Канал публичный",
                    show_alert=True
                )
                return

        post_text = f"{post.topic} \n {post.text} \n Категория: {post.category}"

        if post.media_ids:
            sent = await bot.send_photo(
                chat_id=chat_id,
                photo=post.media_ids[0],
                caption=post_text,
                parse_mode='HTML'
            )
        else:
            sent = await bot.send_photo(
                chat_id=chat_id,
                caption=post_text,
                parse_mode='HTML'
            )

        storage.update_post(
            post_id,
            status='published',
            moderated_by=user_id,
            moderated_at=datetime.now(),
            channel_message_id=sent.message_id,
            channel_post_url=sent.get_url()
        )

        # Отсылаем уведомление студенту при публикации
        try:
            await bot.send_message(
                post.user_id,
                f"✅ Ваша новость опубликована! Смотреть: {sent.get_url()}"
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление автору {post.user_id}: {e}")
        #

        # Показываем панель администратора
        await show_admin_panel(callback.message, user_id)

        await callback.answer("Новость одобрена!")
    else:
        await callback.answer("Сначала укажите канал в настройках.")
        return
    

@admin_router.callback_query(lambda c: c.data.startswith("revision_"))
async def revision_post(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    post_id = int(callback.data.split('_')[1])
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return

    if post.taken_by and post.taken_by != user_id:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        await callback.answer(f"Пост уже взял {admin_name}", show_alert=True)
        return

    if not post.taken_by:
        storage.update_post(post_id, taken_by=user_id, taken_at=datetime.now())

    await state.update_data(post_id=post_id)
    await state.set_state(AdminState.wait_for_comment)

    await callback.message.answer(
        f"Возврат новости #{post_id} на доработку.\nНапишите комментарий для автора (что нужно исправить):"
    )
    await callback.answer()


@admin_router.callback_query(lambda c: c.data.startswith("reject_") and not c.data.startswith("confirm_reject_") and not c.data.startswith("cancel_reject_"))
async def reject_post(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    parts = callback.data.split('_')
    if len(parts) < 2 or not parts[1].isdigit():
        await callback.answer(
            "Неверный формат запроса. Используйте кнопки с ID поста.",
            show_alert=True
        )
        return

    post_id = int(parts[1])
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return

    if post.taken_by and post.taken_by != user_id:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        await callback.answer(f"Пост уже взял {admin_name}", show_alert=True)
        return

    if not post.taken_by:
        storage.update_post(post_id, taken_by=user_id, taken_at=datetime.now())

    await callback.message.answer(
        f"Вы точно хотите отклонить пост #{post_id}?\n"
        f"Текст поста:\n{post.text}", 
        reply_markup=keyboards.confirm_desicion_to_delete(post_id)
    )
    

@admin_router.message(AdminState.wait_for_reject_comment)
async def process_reject_comment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("У вас нет прав администратора.")
        await state.clear()
        return

    data = await state.get_data()
    post_id = data.get('post_id')
    if not post_id:
        await message.answer("Ошибка: не найден ID поста. Попробуйте снова.")
        await state.clear()
        return

    comment = message.text
    if len(comment) < 10:
        await message.answer("Причина отклонения должна содержать минимум 10 символов. Напишите подробнее:")
        return

    post = storage.get_post(post_id)
    if not post:
        await message.answer("Пост не найден")
        await state.clear()
        return

    storage.update_post(
        post_id,
        status='rejected',
        moderated_by=user_id,
        moderated_at=datetime.now(),
        comment=comment
    )

    # отсылаем уведомление автору поста при оотклонении
    try:
        await bot.send_message(
            post.user_id,
            f"Ваша новость \"{post.topic}\" (ID #{post_id}) отклонена.\n"
            f"Причина: {comment}"
        )
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление автору {post.user_id}: {e}")
    # 

    await message.answer(f"✅ Новость #{post_id} отклонена. Причина отправлена автору.")

    # вызываем панель администратора (с удалением старой клавиатуры)
    await show_admin_panel(message, user_id)

    await state.clear()


@admin_router.callback_query(lambda c: c.data.startswith("confirm_reject_"))
async def confirm_rejecting_post(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    parts = callback.data.split('_')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer(
            "Неверный формат запроса. Используйте кнопки с ID поста.",
            show_alert=True
        )
        return

    post_id = int(parts[2])
    
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    
    storage.update_post(
        post_id,
        status='rejected',
        moderated_by=user_id,
        moderated_at=datetime.now()
    )

    # Запоминаем ID поста, переключаемся на ввод комментария
    await state.update_data(post_id=post_id)
    await state.set_state(AdminState.wait_for_reject_comment)

    await callback.message.answer(
        f"Отклонение новости #{post_id}.\nНапишите причину отклонения для автора (минимум 10 символов):"
    )
    await callback.answer()


@admin_router.callback_query(lambda c: c.data.startswith("cancel_reject_"))
async def cancel_rejecting_post(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    parts = callback.data.split('_')
    if len(parts) < 3 or not parts[2].isdigit():
        await callback.answer(
            "Неверный формат запроса. Используйте кнопки с ID поста.",
            show_alert=True
        )
        return

    post_id = int(parts[2])
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return

    await callback.message.edit_text(
        f"Отмена отклонения поста #{post_id}\n\n"
        f"Пост возвращен на модерацию."
    )
    
    # Показываем панель администратора
    await show_admin_panel(callback.message, user_id)


# ЭКСПОРТ
@admin_router.callback_query(lambda c: c.data.startswith("export_"))
async def export_post(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    post_id = int(callback.data.split('_')[1])
    post = storage.get_post(post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return

    zip_data = io.BytesIO()
    with zipfile.ZipFile(zip_data, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        data = post.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)
        zip_file.writestr(f"post_{post_id}.json", json_str.encode('utf-8'))

        media_files = await download_post(post, post_id)
        for filename, file_data in media_files.items():
            zip_file.writestr(f"media/{filename}", file_data)

    zip_data.seek(0)
    zip_file = BufferedInputFile(zip_data.getvalue(), filename=f"post_{post_id}.zip")

    await callback.message.answer_document(
        document=zip_file,
        caption=f"Выгрузка новости #{post_id}"
    )
    await callback.answer("Архив выгружен!")


async def download_post(post, post_id):
    files_dict = {}

    if hasattr(post, 'photo') and post.photo:
        for i, photo_size in enumerate(post.photo):
            file_id = photo_size[-1].file_id
            file_data = await download_file(file_id)
            if file_data:
                file_name = f"photo_{i + 1}.jpg"
                files_dict[file_name] = file_data

    if hasattr(post, 'document') and post.document:
        file_data = await download_file(post.document.file_id)
        if file_data:
            file_name = post.document.file_name
            files_dict[file_name] = file_data


async def download_file(file_id):
    try:
        file_info = await bot.get_file(file_id)
        file_content = await bot.download_file(file_info.file_path)
        return file_content
    except Exception as e:
        print("Ошибка при скачивании файла: {e}")
        return


@admin_router.message(AdminState.wait_for_comment)
async def process_comment(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("У вас нет прав администратора.")
        await state.clear()
        return

    data = await state.get_data()
    post_id = data.get('post_id')
    comment = message.text

    if len(comment) < 10:
        await message.answer("Комментарий должен содержать минимум 10 символов. Напишите подробнее:")
        return

    post = storage.get_post(post_id)
    if not post:
        await message.answer("Пост не найден")
        await state.clear()
        return
    
    storage.update_post(
        post_id,
        status='revision',
        moderated_by=user_id,
        moderated_at=datetime.now(),
        comment=comment
    )
    # Отсылаем уведомление студенту о возврате на доработку
    try:
        await bot.send_message(
            post.user_id,
            f"🔗 Ваша новость \"{post.topic}\" требует правок. "
            f"Комментарий модератора: {comment}. "
            f"Исправьте, нажав кнопку ниже.",
            reply_markup=keyboards.edit_revision_button
        )
        from aiogram.fsm.storage.base import StorageKey
        from aiogram.fsm.context import FSMContext
        
        storage_key = StorageKey(bot_id=bot.id, user_id=post.user_id, chat_id=post.user_id)
        student_context = FSMContext(storage=_dispatcher.storage, key=storage_key)
        await student_context.set_state(UserState.edit_revision_news)
        await student_context.update_data(
            pending_edit_post_id=post.id,
            pending_edit_topic=post.topic,
            pending_edit_text=post.text,
            # pending_edit_files=[] if hasattr(post, 'files') else post.files,
            pending_edit_comment=comment,
            # pending_edit_user_id=post.user_id
        )
        
        logger.info(f"Уведомление отправлено автору {post.user_id}, состояние установлено.")

    except Exception as e:
        logger.error(f"Не удалось отправить уведомление автору {post.user_id}: {e}")

    await message.answer(f"Новость #{post_id} возвращена автору.\nКомментарий: {comment}")
    await state.clear()


# кнопка "настройки" для админа
@admin_router.callback_query(lambda c: c.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    keyboard = keyboards.get_admin_settings_keyboard()
    await callback.message.edit_text(
        "Настройки.\n Здесь можно настроить канал для публикации.",
        reply_markup=keyboard
    )
    await callback.answer()

# кнопка установки канала
@admin_router.callback_query(lambda c: c.data == "admin_set_channel")
async def admin_set_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Только админ может настраивать канал.", show_alert=True)
        return

    await state.set_state(AdminState.wait_for_channel)
    await callback.message.edit_text(
        "Установка канала.\n Введите ID канала (например, https://t.me/newsbottest100)\nили username канала (например, @newsbottest100):",
        reply_markup=keyboards.back_to_admin
    )
    await callback.answer()


@admin_router.message(AdminState.wait_for_channel)
async def process_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        await state.clear()
        return

    channel = message.text.strip()
    if channel.startswith('@'):
        storage.set_setting('channel_username', channel)
        storage.set_setting('channel_link', None)
    elif channel.startswith('https://t.me/'):
        storage.set_setting('channel_link', channel)
        storage.set_setting('channel_username', None)

    await message.answer(f"Канал установлен: {channel}", reply_markup=keyboards.back_to_admin)
    await state.clear()

# кнопка "назад"
@admin_router.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    if not is_admin(user_id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    
    await show_admin_panel(callback.message, user_id)
    await callback.answer()


@admin_router.callback_query(lambda c: c.data == "admin_manage")
async def admin_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "Выберите действие:",
        reply_markup=keyboards.add_admin_keyboard
    )
    await callback.answer()
    await state.clear()


@admin_router.callback_query(lambda c: c.data == "admin_list")
async def admin_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    
    admins = storage.get_all_admins()
    
    if not admins:
        text = "Список администраторов пуст."
    else:
        text = "Список администраторов:\n\n"
        for i, admin in enumerate(admins, 1):
            role = "Суперадмин" if admin.role == 'superadmin' else "Админ"
            text += f"{i}. @{admin.username} (ID: {admin.user_id}) - {role}\n"
    
    await callback.message.answer(text, reply_markup=keyboards.add_admin_keyboard)
    await callback.answer()


# =========== СТАТИСТИКА ===========
@admin_router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    stats = storage.get_stats()
    text = "Статистика постов:\n\n"
    text += f"Всего: {stats['total']}\n"
    text += f"Черновики: {stats['draft']}\n"
    text += f"На модерации: {stats['pending']}\n"
    text += f"На доработке: {stats['revision']}\n"
    text += f"Одобрено: {stats['approved']}\n"
    text += f"Опубликовано: {stats['published']}\n"
    text += f"Отклонено: {stats['rejected']}\n"

    await callback.message.edit_text(text, reply_markup=keyboards.back_to_admin)
    await callback.answer()