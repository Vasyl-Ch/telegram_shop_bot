"""
Handler for the /start command and the main menu."""

import logging
import telebot
from telebot import types

from config.settings import settings
from presentation.keyboards.main_keyboards import get_main_menu_keyboard

logger = logging.getLogger(__name__)


def register_start_handlers(bot: telebot.TeleBot, user_limit_repo=None) -> None:
    """
    Registers handlers for the /start command.

    Args:
        bot: Telegram bot instance
        user_limit_repo: User Limit Repository (optional)
    """

    @bot.message_handler(commands=["start"])
    def handle_start(message: types.Message) -> None:
        """The /start command handler."""

        if user_limit_repo:
            limit = user_limit_repo.get(message.chat.id)
            if limit and limit.is_banned:
                ban_message = (
                    "🚫 <b>Доступ к боту заблокирован</b>\n\n"
                    f"<b>Причина:</b> {limit.ban_reason or 'не указана'}\n\n"
                )

                if limit.banned_at:
                    ban_date = limit.banned_at.strftime("%d.%m.%Y %H:%M")
                    ban_message += f"<b>Дата блокировки:</b> {ban_date}\n\n"

                ban_message += (
                    "Для разблокировки свяжитесь с администратором.\n"
                    "Используйте кнопку '💬 Связаться с менеджером' ниже."
                )

                bot.send_message(
                    message.chat.id,
                    ban_message,
                    parse_mode="HTML",
                    reply_markup=get_main_menu_keyboard(),
                )
                return

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

    @bot.message_handler(func=lambda m: m.text == "💬 Связаться с менеджером")
    def handle_contact_manager(message: types.Message) -> None:
        """Handler of the 'Contact manager' button."""
        try:
            support_manager_id = settings.support_manager_id

            if support_manager_id.startswith("@"):
                manager_link = f"https://t.me/{support_manager_id[1:]}"
            else:
                manager_link = f"tg://user?id={support_manager_id}"

            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton(
                    text="💬 Написать менеджеру", url=manager_link
                )
            )

            bot.send_message(
                message.chat.id,
                "💬 <b>Связаться с менеджером</b>\n\n"
                "Нажмите кнопку ниже, чтобы написать менеджеру.\n"
                "Мы ответим вам в ближайшее время!",
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        except Exception as e:
            logger.error(f"Error in contact manager handler: {e}")
            bot.send_message(
                message.chat.id,
                "❌ Ошибка получения контакта менеджера. "
                "Попробуйте позже или свяжитесь через /help",
            )


def _send_welcome(bot: telebot.TeleBot, chat_id: int) -> None:
    """
    Sends a welcome message.

    Args:
        bot: Bot instance
        chat_id: Chat ID
    """
    is_seller = str(chat_id) == str(settings.seller_chat_id)

    if is_seller:
        from presentation.keyboards.main_keyboards import get_seller_main_keyboard

        welcome_text = (
            "👨‍💼 <b>Добро пожаловать в панель продавца!</b>\n\n"
            "Используйте кнопки ниже для управления магазином:"
        )
        keyboard = get_seller_main_keyboard()
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("seller", "Панель продавца"),
            types.BotCommand("help", "Помощь"),
        ]
    else:
        welcome_text = (
            "🛒 <b>Добро пожаловать в наш магазин!</b>\n\n"
            "Используйте кнопки ниже для навигации:"
        )
        keyboard = get_main_menu_keyboard()
        commands = [
            types.BotCommand("start", "Главное меню"),
            types.BotCommand("help", "Помощь"),
            types.BotCommand("catalog", "Каталог товаров"),
            types.BotCommand("cart", "Корзина"),
            types.BotCommand("orders", "Мои заказы"),
        ]

    bot.send_message(
        chat_id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )
    bot.set_my_commands(commands)
