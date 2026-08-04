from aiogram.types import (ReplyKeyboardMarkup, KeyboardButton, 
                           InlineKeyboardMarkup, InlineKeyboardButton)

edit_news = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отправить"), KeyboardButton(text="Редактировать")]],
                                        resize_keyboard=True,
                                        input_field_placeholder="Выберите действие",
                                        one_time_keyboard=True)

choose_tags = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='Мероприятие')],
    [KeyboardButton(text='Стипендия')],
    [KeyboardButton(text='Спорт')],
    [KeyboardButton(text='Обучение')]],
    resize_keyboard=True,
    input_field_placeholder="Выберите тэги",
    one_time_keyboard=True
)