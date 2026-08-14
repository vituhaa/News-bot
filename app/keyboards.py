from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton, 
                           ReplyKeyboardRemove)


# ========== КЛАВИАТУРА ПОЛЬЗОВАТЕЛЯ ==========
edit_news_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Отправить"), KeyboardButton(text="Редактировать")]],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
    one_time_keyboard=True)

make_another_news = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие")

# Категории
category_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Мероприятие')],
    [KeyboardButton(text='Стипендия')],
    [KeyboardButton(text='Спорт')],
    [KeyboardButton(text='Обучение')]],
    resize_keyboard=True,
    input_field_placeholder="Выберите категорию",
    one_time_keyboard=True
)

done_keyboard = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Готово')]],
    resize_keyboard=True,
    one_time_keyboard=True
)

# ========== КЛАВИАТУРА АДМИНИСТРАТОРА ==========

# Основная панель
def get_admin_main_keyboard(pending_count: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Входящие ({pending_count})", callback_data="admin_inbox")],
        [InlineKeyboardButton(text="Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="Настройки", callback_data="admin_settings")],
        [InlineKeyboardButton(text="Управление админами", callback_data="admin_manage")] 
    ])

# Клавиатура для модерации
def get_admin_post_keyboard(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Одобрить", callback_data=f"approve_{post_id}"),
        InlineKeyboardButton(text="На доработку", callback_data=f"revision_{post_id}")],

        [InlineKeyboardButton(text="Отклонить", callback_data=f"reject_{post_id}"),
        InlineKeyboardButton(text="Выгрузить JSON", callback_data=f"export_{post_id}")],

        [InlineKeyboardButton(text="Следующий", callback_data="admin_next")]
    ])

def confirm_desicion_to_delete(post_id: int) -> InlineKeyboardMarkup: 
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"confirm_reject_{post_id}"),
        InlineKeyboardButton(text="Нет", callback_data=f"cancel_reject_{post_id}")],
    ])

# Клавиатура настроек
def get_admin_settings_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Установить канал", callback_data="admin_set_channel")],
        [InlineKeyboardButton(text="Управление категориями", callback_data="admin_categories")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
    ])

# Управление админами
def get_admin_manage_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="Список админов", callback_data="admin_list")],
        [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
    ])

# Клавиатура для возврата в главн меню
back_to_admin = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Назад", callback_data="admin_back")]
])

# ========== КЛАВИАТУРА СУПЕРАДМИНИСТРАТОРА ==========
super_admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text='Добавить админа')],
        [KeyboardButton(text='Список текущих админов')],
        [KeyboardButton(text='Удалить админа')]
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите действие",
    one_time_keyboard=True
)