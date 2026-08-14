from aiogram import Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram import Bot
from datetime import datetime
import logging
import json
import os
import re
from io import BytesIO
from dotenv import load_dotenv

from app.storage import storage
from app.models import Post, Admin
import app.keyboards as keyboards

load_dotenv()

admin_router = Router()
logger = logging.getLogger(__name__)

ADMINS = os.getenv("ADMINS", "")
admins_list = [x.strip() for x in ADMINS.split(",") if x.strip()]

SUPER_ADMINS = os.getenv("SUPER_ADMINS", "")
super_admins_list = [x.strip() for x in SUPER_ADMINS.split(",") if x.strip()]

BOT_TOKEN = os.getenv('BOT_TOKEN')
PROXY_URL = os.getenv('PROXY_URL')

session = AiohttpSession(proxy=PROXY_URL)
bot = Bot(token=BOT_TOKEN, session=session)

class AdminState(StatesGroup):
    wait_for_choice = State()
    delete_admin = State()
    wait_for_comment = State()
    wait_for_channel = State()
    wait_for_user_id = State()

def is_admin(user_id: int) -> bool:
    return storage.is_admin(user_id) or (str(user_id) in admins_list)

def is_superadmin(user_id: int) -> bool:
    return storage.is_superadmin(user_id) or (str(user_id) in super_admins_list)

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


# =========== АДМИН ===========
@admin_router.message(Command("admin"))
async def start_admin(message: Message, state: FSMContext):
    user = message.from_user
    if not is_admin(user.id):
        await message.answer("У вас нет прав администратора.")
        return

    pending_count = storage.get_pending_count()

    text = f"Панель администратора\n\n"
    text += f"Новостей в очереди: {pending_count}\n"
    text += f"Всего администраторов: {len(storage.get_all_admins())}\n"

    channel_info = storage.get_channel_info()
    if channel_info['is_configured']:
        channel_display = channel_info.get('channel_username') or channel_info.get('channel_link')
        text += f"Канал: {channel_display}\n"
    else:
        text += "Канал не настроен\n"

    keyboard = keyboards.get_admin_main_keyboard(pending_count)
    await message.answer(text, reply_markup=keyboard)

# =========== СУПЕРАДМИН ===========
@admin_router.message(Command("super"))
async def start_super_admin(message: Message, state: FSMContext):
    user = message.from_user
    if is_superadmin(user.id):
        await message.answer("Выберите действие", reply_markup=keyboards.super_admin_keyboard)
        await state.set_state(AdminState.wait_for_choice)
    else:
        await message.answer("У вас нет прав суперадминистратора.")

@admin_router.message(AdminState.wait_for_choice)
async def process_super_choice(message: Message, state: FSMContext):
    if message.text == "Добавить админа":
        await state.set_state(AdminState.wait_for_user_id)
        await message.answer(
            "Введите телеграм-ID нового администратора:",
            reply_markup=ReplyKeyboardRemove()
        )
    elif message.text == "Список текущих админов":
        admins = storage.get_all_admins()
        if not admins:
            text = "Список администраторов пуст."
        else:
            text = "Список администраторов:\n"
            for i, admin in enumerate(admins, 1):
                role = "Суперадмин" if admin.role == 'superadmin' else "Админ"
                text += f"{i}. @{admin.username} (ID: {admin.user_id}) - {role}\n"
        await message.answer(text, reply_markup=keyboards.super_admin_keyboard)
        # await state.clear()
    elif message.text == "Удалить админа":
        await state.set_state(AdminState.delete_admin)
        await message.answer(
            "Удаление администратора.\n\nВведите Telegram ID пользователя, которого нужно удалить:"
        )
    else:
        await message.answer(
            "Неверная команда. Выберите из предложенных кнопок.",
            reply_markup=keyboards.super_admin_keyboard
        )

@admin_router.message(AdminState.delete_admin)
async def process_delete_admin(message: Message, state: FSMContext):
    try:
        delete_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ввод! Введите числовой ID (например, 123456789):")
        return
    
    if not storage.get_admin(delete_admin_id):
        await message.answer(
            "Этот пользователь не является администратором.",
            reply_markup=keyboards.super_admin_keyboard
        )
        await state.set_state(AdminState.wait_for_choice)
        return
    
    storage.remove_admin(delete_admin_id)
    await message.answer(
        f"Администратор удалён: {delete_admin_id}",
        reply_markup=keyboards.super_admin_keyboard
    )
    await state.set_state(AdminState.wait_for_choice)


@admin_router.message(AdminState.wait_for_user_id)
async def process_new_admin(message: Message, state: FSMContext):
    try:
        new_admin_id = int(message.text.strip())
    except ValueError:
        await message.answer("Неверный ввод! Введите числовой ID (например, 123456789):")
        return

    if storage.get_admin(new_admin_id):
        await message.answer(
            "Этот пользователь уже является администратором.",
            reply_markup=keyboards.super_admin_keyboard
        )
        await state.set_state(AdminState.wait_for_choice)
        return

    admin = Admin(
        user_id=new_admin_id,
        username=f"id_{new_admin_id}",
        role='admin',
        added_by=message.from_user.id
    )
    storage.add_admin(admin)

    await message.answer(
        f"Новый администратор добавлен: {new_admin_id}",
        reply_markup=keyboards.super_admin_keyboard
    )
    await state.set_state(AdminState.wait_for_choice)


# Посты, приходящие администратоам
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
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    pending_posts = storage.get_pending_posts()
    if not pending_posts:
        await callback.message.edit_text("Все новости обработаны!")
        await callback.answer()
        return

    post = pending_posts[0]
    await show_post_to_admin(callback.message, post)
    await callback.answer()

async def show_post_to_admin(message: Message, post: Post):
    text = format_post_text(post)
    keyboard = keyboards.get_admin_post_keyboard(post.id)

    if post.media_ids and post.media_ids[0]:
        try:
            if post.media_types[0] == 'photo':
                await message.answer_photo(
                    photo=post.media_ids[0],
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                await message.answer_document(
                    document=post.media_ids[0],
                    caption=text,
                    reply_markup=keyboard
                )
            return
        except Exception as e:
            logger.error(f"Ошибка отправки медиа: {e}")

    await message.answer(text, reply_markup=keyboard)

# =========== МОДЕРАЦИЯ ===========
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
        for i, name in enumerate(post.media_names, 1):
            text += f"  {i}. {name}\n"
    if post.comment:
        text += f"\nКОММЕНТАРИЙ:\n{post.comment}\n"
    return text

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

    if post.status == 'pending' and post.taken_by and post.taken_by != user_id:
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

        post_text = f"{post.topic} \n {post.text} \n Тэг: {post.category}"

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

    if post.status == 'pending' and post.taken_by and post.taken_by != user_id:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        await callback.answer(f"Пост уже взял {admin_name}", show_alert=True)
        return

    if not post.taken_by:
        storage.update_post(post_id, taken_by=user_id, taken_at=datetime.now())

    await state.update_data(post_id=post_id)
    await state.set_state(AdminState.wait_for_comment)

    await callback.message.edit_text(
        f"Возврат новости #{post_id} на доработку.\nНапишите комментарий для автора (что нужно исправить):"
    )
    await callback.answer()


@admin_router.callback_query(lambda c: c.data.startswith("reject_") and not c.data.startswith("confirm_reject_") and not c.data.startswith("cancel_reject_"))
async def reject_post(callback: CallbackQuery):
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

    if post.status == 'pending' and post.taken_by and post.taken_by != user_id:
        admin = storage.get_admin(post.taken_by)
        admin_name = f"@{admin.username}" if admin else f"id{post.taken_by}"
        await callback.answer(f"Пост уже взял {admin_name}", show_alert=True)
        return

    if not post.taken_by:
        storage.update_post(post_id, taken_by=user_id, taken_at=datetime.now())

    await callback.message.answer(
        f"Вы точно хотите отклонить пост #{post_id}?\n\n"
        f"Текст поста:\n{post.text}", 
        reply_markup=keyboards.confirm_desicion_to_delete(post_id)
    )

    await callback.answer()


@admin_router.callback_query(lambda c: c.data.startswith("confirm_reject_"))
async def confirm_rejecting_post(callback: CallbackQuery):
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
    
    await callback.message.edit_text(f"Новость #{post_id} отклонена.")
    await callback.message.answer("Панель администратора: ", reply_markup=keyboards.get_admin_main_keyboard())


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
    
    await callback.message.answer("Панель администратора: ", reply_markup=keyboards.get_admin_main_keyboard())


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

    data = post.to_dict()
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    file = BytesIO(json_str.encode('utf-8'))
    file.name = f"post_{post_id}.json"

    await callback.message.answer_document(
        document=file,
        caption=f"Выгрузка новости #{post_id}"
    )
    await callback.answer("JSON выгружен!")


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

    await message.answer(f"Новость #{post_id} возвращена автору.\nКомментарий: {comment}")
    await state.clear()

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

    await callback.message.edit_text(text)
    await callback.answer()

# =========== НАСТРОЙКИ ===========

@admin_router.callback_query(lambda c: c.data == "admin_settings")
async def admin_settings(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return

    keyboard = keyboards.get_admin_settings_keyboard()
    await callback.message.edit_text(
        "Настройки:\n\nЗдесь можно настроить канал для публикации.",
        reply_markup=keyboard
    )
    await callback.answer()

@admin_router.callback_query(lambda c: c.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("У вас нет прав администратора.", show_alert=True)
        return
    # Просто перезапускаем панель
    await start_admin(callback.message, None)
    await callback.answer()