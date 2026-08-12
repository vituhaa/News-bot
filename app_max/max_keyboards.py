from maxapi.keyboards import InlineKeyboardMarkup, InlineKeyboardButton

CATEGORIES = ['Мероприятие', 'Стипендия', 'Спорт', 'Обучение']

def get_category_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для выбора категории"""
    buttons = []
    for cat in CATEGORIES:
        buttons.append([InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_done_keyboard() -> InlineKeyboardMarkup:
    """Кнопка 'Готово' для завершения загрузки файлов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Готово", callback_data="files_done")]
    ])

def get_edit_submit_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с выбором 'Отправить' или 'Редактировать'"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Отправить на модерацию", callback_data="submit_news")],
        [InlineKeyboardButton(text="Редактировать", callback_data="edit_news")]
    ])