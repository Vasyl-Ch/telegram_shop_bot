"""
ReplyKeyboard keyboard (persistent menu at the bottom)."""

from telebot import types


def get_main_menu_keyboard() -> types.ReplyKeyboardMarkup:
    """
    The main menu of the bot.

    Returns:
        ReplyKeyboardMarkup: Main Menu Keyboard
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
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
        types.KeyboardButton("💬 Связаться с менеджером"),
    )
    return markup


def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    """
    Keyboard with an undo button (for step-by-step forms).

    Returns:
        ReplyKeyboardMarkup: Undo keyboard
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add(types.KeyboardButton("❌ Отменить оформление"))
    return markup


def get_seller_main_keyboard() -> types.ReplyKeyboardMarkup:
    """
    The keypad of the seller's main menu.

    Returns:
        ReplyKeyboardMarkup: Seller's Keyboard
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.row(
        types.KeyboardButton("📋 Активные заказы"),
        types.KeyboardButton("✅ Выполненные"),
    )
    markup.row(
        types.KeyboardButton("🗂 Заказы"),
        types.KeyboardButton("💳 Платежи"),
    )
    markup.row(
        types.KeyboardButton("👥 Управление пользователями"),
        types.KeyboardButton("📊 Статистика"),
    )
    markup.row(
        types.KeyboardButton("⚠️ Мало на складе"),
        types.KeyboardButton("🔄 Обновить каталог"),
    )
    return markup
