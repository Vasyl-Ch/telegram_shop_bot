"""
ReplyKeyboard клавиатуры (постоянное меню снизу).
"""

from telebot import types


def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Главное меню бота.

    Returns:
        ReplyKeyboardMarkup: Клавиатура главного меню
    """
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )
    markup.row(
        types.KeyboardButton("🗂 Категории"),
        types.KeyboardButton("📋 Каталог"),
    )
    markup.row(
        types.KeyboardButton("🛍 Корзина"),
        types.KeyboardButton("🔍 Поиск"),
    )
    markup.row(
        types.KeyboardButton("📦 Мои заказы"),
        types.KeyboardButton("🔄 Обновить"),
    )
    return markup


def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Клавиатура с кнопкой отмены (для step-by-step форм).

    Returns:
        ReplyKeyboardMarkup: Клавиатура с отменой
    """
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=1
    )
    markup.add(types.KeyboardButton("❌ Отменить оформление"))
    return markup


def get_seller_main_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Клавиатура главного меню продавца.

    Returns:
        ReplyKeyboardMarkup: Клавиатура продавца
    """
    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        row_width=2
    )
    markup.row(
        types.KeyboardButton("📋 Активные заказы"),
        types.KeyboardButton("✅ Выполненные"),
    )
    markup.row(
        types.KeyboardButton("📊 Статистика"),
        types.KeyboardButton("⚠️ Мало на складе"),
    )
    markup.row(
        types.KeyboardButton("🔄 Обновить каталог"),
    )
    return markup