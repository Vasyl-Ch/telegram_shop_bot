"""
Handler for the /start command and the main menu."""

import logging
import telebot
from telebot import types

from presentation.keyboards.main_keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)


def register_start_handlers(bot: telebot.TeleBot) -> None:
    """
    Registers handlers for the /start command.

    Args:
        bot: Telegram bot instance
    """

    @bot.message_handler(commands=["start"])
    def handle_start(message: types.Message) -> None:
        """The /start command handler."""
        param = None
        if message.text and " " in message.text:
            param = message.text.split(" ", 1)[1]

        if param == "payment_success":
            bot.send_message(
                message.chat.id,
                "✅ <b>Оплата прошла успешно!</b>\n\n"
                "Ваш заказ подтверждён. Ожидайте уведомления от менеджера.",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        if param == "payment_cancelled":
            bot.send_message(
                message.chat.id,
                "❌ <b>Оплата отменена.</b>\n\n"
                "Вы можете повторить попытку через раздел «📦 Мои заказы».",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        _send_welcome(bot, message.chat.id)

    @bot.message_handler(commands=["help"])
    def handle_help(message: types.Message) -> None:
        """The /help command handler."""
        help_text = (
            "🛒 <b>Добро пожаловать в магазин!</b>\n\n"
            "Доступные команды:\n"
            "🗂 <b>Категории</b> — просмотр по разделам\n"
            "📋 <b>Каталог</b> — все товары\n"
            "🛍 <b>Корзина</b> — ваши выбранные товары\n"
            "📦 <b>Мои заказы</b> — история заказов\n"
            "🔍 <b>Поиск</b> — найти товар по названию\n"
            "🔄 <b>Обновить</b> — обновить каталог\n\n"
            "По вопросам: напишите менеджеру."
        )
        bot.send_message(
            message.chat.id,
            help_text,
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )


def _send_welcome(bot: telebot.TeleBot, chat_id: int) -> None:
    """
    Sends a welcome message.

    Args:
        bot: Bot instance
        chat_id: Chat ID
    """
    welcome_text = (
        "🛒 <b>Добро пожаловать в наш магазин!</b>\n\n"
        "Используйте кнопки ниже для навигации:"
    )
    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
    bot.set_my_commands(
        [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("help", "Помощь"),
            types.BotCommand("catalog", "Каталог товаров"),
            types.BotCommand("cart", "Корзина"),
            types.BotCommand("orders", "Мои заказы"),
        ]
    )
