from maxapi import Router, Bot, F
from maxapi.types import MessageCreated, CallbackQueryCreated, InputMediaPhoto
from maxapi.filters.command import Command
from maxapi.fsm import State, StatesGroup, FSMContext
from datetime import datetime
import logging
import json
import os
import re
from dotenv import load_dotenv

from app.storage import storage
from app.models import Post, Admin
import app_max.max_keyboards as keyboards

load_dotenv()

admin_router = Router()
logger = logging.getLogger(__name__)

ADMINS = os.getenv("ADMINS", "")
admins_list = [int(x.strip()) for x in ADMINS.split(",") if x.strip()]
admin_page = {}

class AdminState(StatesGroup):
    wait_for_choice = State()
    delete_admin = State()
    wait_for_comment = State()
    wait_for_reject_comment = State()
    wait_for_channel = State()
    wait_for_user_id = State()

def is_admin(user_id: int) -> bool:
    return user_id in admins_list

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


@admin_router.message_created(Command("admin"))
async def start_admin(event: MessageCreated):
    user_id = event.from_user.id
    if not is_admin(user_id):
        await event.message.answer("У вас нет прав администратора.")
        return
    await show_admin_panel(event.message, user_id)

async def show_admin_panel(message: MessageCreated, user_id: int):
    pending_posts = storage.get_pending_count()
    text = f"Панель администратора\n\nНовостей в очереди: {pending_posts}\n"

    admins = storage.get_all_admins()
    text += f"Всего администраторов: {len(admins)}\n"
    channel_info = storage.get_channel_info()
    if channel_info['is_configured']:
        channel_display = channel_info.get('channel_username') or channel_info.get('channel_link')
        text += f"Канал: {channel_display}\n"
    else:
        text += "Канал не настроен\n"

    keyboard = keyboards.get_admin_main_keyboard(pending_posts)
    await message.answer(text, reply_markup=keyboard)

@admin_router.message_created(Command("review"))
async def review_post_by_id(event: MessageCreated):
    """Переход к заявке по ID (/review 123)"""
    user_id = event.from_user.id
    if not is_admin(user_id):
        await event.message.answer("У вас нет прав администратора.")
        return

    args = event.message.body.text.split(maxsplit=1)
    if len(args) < 2:
        await event.message.answer("Укажите ID новости, например: /review 123")
        return

    try:
        post_id = int(args[1])
    except ValueError:
        await event.message.answer("ID должен быть числом.")
        return

    post = storage.get_post(post_id)
    if not post:
        await event.message.answer(f"Новость с ID {post_id} не найдена.")
        return

    await show_post_to_admin(event.message, post, show_next=False)
    
@admin_router.callback_query_created(F.data == "admin_inbox")
async def admin_inbox(callback: CallbackQueryCreated):
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

async def show_post_to_admin(message: MessageCreated, post: Post, progress: str = "", show_next: bool = True):
    text = format_post_text(post)
    if progress:
        text = f"{progress}\n{text}"
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

    if photos:
        if len(photos) == 1:
            await message.answer_photo(photo=photos[0], caption=text, reply_markup=keyboard)
        else:
            # В MAX тоже есть send_media_group, но для первого фото с caption используем отдельный вызов
            await message.answer_photo(photo=photos[0], caption=text, reply_markup=keyboard)
            if len(photos) > 1:
                album = [InputMediaPhoto(media=photo_id) for photo_id in photos[1:]]
                # Используем bot.send_media_group, так как у message нет прямого метода
                await message.bot.send_media_group(
                    chat_id=message.chat.id,
                    media=album
                )
    elif documents:
        await message.answer_document(document=documents[0], caption=text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)