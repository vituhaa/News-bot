from aiogram import Router
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from datetime import datetime
import logging
import json
import os
from io import BytesIO

from app.storage import storage
from app.models import Post, Admin
import app.keyboards as keyboards

admin_router = Router()
logger = logging.getLogger(__name__)

ADMINS = os.getenv("ADMINS")
SUPER_ADMINS = os.getenv("SUPER_ADMINS")
admins_list = ADMINS.split(',') if ADMINS else []
super_admins_list = SUPER_ADMINS.split(',') if SUPER_ADMINS else []

class AdminState(StatesGroup):
    wait_for_choice = State()
    wait_for_comment = State()
    wait_for_channel = State()
    wait_for_user_id = State()

def is_admin(user_id: int) -> bool:
    return storage.is_admin(user_id) or (str(user_id) in admins_list)

def is_superadmin(user_id: int) -> bool:
    return storage.is_superadmin(user_id) or (str(user_id) in super_admins_list)

def init_admins(SUPER_ADMINS):
    for admin_id in SUPER_ADMINS:
        if not storage.get_admin(admin_id):
            admin = Admin(
                user_id=admin_id,
                username=f"superadmin_{admin_id}",
                role='superadmin',
                added_by=admin_id
            )
            storage.add_admin(admin)
            logger.info(f"Суперадмин {admin_id} инициализирован")

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
        channel_display = channel_info.get('channel_username') or channel_info.get('channel_id')
        text += f"Канал: {channel_display}\n"
    else:
        text += "Канал не настроен\n"

    keyboard = keyboards.get_admin_main_keyboard(pending_count)
    await message.answer(text, reply_markup=keyboard)

# =========== ТОЛЬКО ДЛЯ СУПЕРАДМИНА ===========
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
        await message.answer(text, reply_markup=ReplyKeyboardRemove())
        await state.clear()
    else:
        await message.answer(
            "Неверная команда. Выберите из предложенных кнопок.",
            reply_markup=keyboards.super_admin_keyboard
        )

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
        await state.clear()
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
    await state.clear()

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

    storage.update_post(
        post_id,
        status='approved',
        moderated_by=user_id,
        moderated_at=datetime.now()
    )

    await callback.message.edit_text(
        f"Новость #{post_id} одобрена!\nАвтор: @{post.username}"
    )
    await callback.answer("Новость одобрена!")

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

@admin_router.callback_query(lambda c: c.data.startswith("reject_"))
async def reject_post(callback: CallbackQuery):
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

    storage.update_post(
        post_id,
        status='rejected',
        moderated_by=user_id,
        moderated_at=datetime.now()
    )

    await callback.message.edit_text(f"Новость #{post_id} отклонена.")
    await callback.answer("Новость отклонена!")

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

@admin_router.callback_query(lambda c: c.data == "admin_set_channel")
async def admin_set_channel(callback: CallbackQuery, state: FSMContext):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Только суперадмин может настраивать канал.", show_alert=True)
        return

    await state.set_state(AdminState.wait_for_channel)
    await callback.message.edit_text(
        "Установка канала\n\nВведите ID канала (например, -1001234567890)\nили username канала (например, @my_channel):"
    )
    await callback.answer()

@admin_router.message(AdminState.wait_for_channel)
async def process_channel(message: Message, state: FSMContext):
    if not is_superadmin(message.from_user.id):
        await message.answer("У вас нет прав суперадминистратора.")
        await state.clear()
        return

    channel = message.text.strip()
    if channel.startswith('@'):
        storage.set_setting('channel_username', channel)
        storage.set_setting('channel_id', None)
    else:
        storage.set_setting('channel_id', channel)
        storage.set_setting('channel_username', None)

    await message.answer(f"Канал установлен: {channel}", reply_markup=ReplyKeyboardRemove())
    await state.clear()

# =========== УПРАВЛЕНИЕ АДМИНАМИ ===========

@admin_router.callback_query(lambda c: c.data == "admin_manage")
async def admin_manage(callback: CallbackQuery):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Только суперадмин может управлять админами.", show_alert=True)
        return

    keyboard = keyboards.get_admin_manage_keyboard()
    await callback.message.edit_text(
        "Управление администраторами:\n\nЗдесь можно добавлять и удалять администраторов.",
        reply_markup=keyboard
    )
    await callback.answer()

@admin_router.callback_query(lambda c: c.data == "admin_add")
async def admin_add(callback: CallbackQuery, state: FSMContext):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Только суперадмин может добавлять админов.", show_alert=True)
        return

    await state.set_state(AdminState.wait_for_user_id)
    await callback.message.edit_text(
        "Добавление администратора\n\nВведите Telegram ID пользователя (число):"
    )
    await callback.answer()

@admin_router.callback_query(lambda c: c.data == "admin_list")
async def admin_list(callback: CallbackQuery):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Только суперадмин может просматривать список.", show_alert=True)
        return

    admins = storage.get_all_admins()
    if not admins:
        text = "Список администраторов пуст."
    else:
        text = "Список администраторов:\n\n"
        for i, admin in enumerate(admins, 1):
            role = "Суперадмин" if admin.role == 'superadmin' else "Админ"
            text += f"{i}. @{admin.username} (ID: {admin.user_id}) - {role}\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="admin_manage")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@admin_router.callback_query(lambda c: c.data == "admin_remove")
async def admin_remove(callback: CallbackQuery, state: FSMContext):
    if not is_superadmin(callback.from_user.id):
        await callback.answer("Только суперадмин может удалять админов.", show_alert=True)
        return

    await state.set_state(AdminState.wait_for_user_id)
    await callback.message.edit_text(
        "Удаление администратора\n\nВведите Telegram ID пользователя, которого нужно удалить:"
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