"""
Обработчики корзины: просмотр, изменение количества, очистка.
"""

import logging
import telebot
from telebot import types

from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.catalog_repository import CatalogRepository
from presentation.keyboards.inline_keyboards import get_cart_keyboard
from utils.formatters import format_cart

logger = logging.getLogger(__name__)


def register_cart_handlers(
    bot: telebot.TeleBot,
    cart_repo: CartRepository,
    catalog_repo: CatalogRepository,
) -> None:
    """
    Регистрирует обработчики корзины.

    Args:
        bot: Инстанс бота
        cart_repo: Репозиторий корзин
        catalog_repo: Репозиторий каталога
    """

    def _send_cart(chat_id: int, message_id: int = None) -> None:
        """Внутренний хелпер: отправляет или обновляет сообщение с корзиной."""
        cart = cart_repo.get_or_create(chat_id)
        text = format_cart(cart)
        keyboard = get_cart_keyboard(cart)

        if message_id:
            try:
                bot.edit_message_text(
                    text=text,
                    chat_id=chat_id,
                    message_id=message_id,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
                return
            except telebot.apihelper.ApiTelegramException as e:
                if "message is not modified" in str(e):
                    return
                logger.debug(f"Edit failed, sending new message: {e}")

        bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    # ──────────────────────────────────────────────
    # Просмотр корзины
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🛍 Корзина")
    @bot.message_handler(commands=["cart"])
    def handle_view_cart(message: types.Message) -> None:
        _send_cart(message.chat.id)

    # ──────────────────────────────────────────────
    # Увеличить количество
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("cart_inc:")
    )
    def handle_cart_increase(call: types.CallbackQuery) -> None:
        product_id = int(call.data.split(":")[1])
        chat_id = call.message.chat.id

        cart = cart_repo.get_or_create(chat_id)
        product = catalog_repo.get_by_id(product_id)

        if not product:
            bot.answer_callback_query(call.id, "Товар не найден.")
            return

        if product_id not in cart.items:
            bot.answer_callback_query(call.id, "Товар не в корзине.")
            return

        current_qty = cart.items[product_id].quantity
        if current_qty >= product.stock:
            bot.answer_callback_query(
                call.id,
                f"Максимальное количество: {product.stock} шт."
            )
            return

        try:
            cart.items[product_id] = cart.items[product_id].increase()
            cart_repo.update(cart)
            bot.answer_callback_query(call.id, "➕ Добавлено")
            _send_cart(chat_id, call.message.message_id)
        except ValueError as e:
            bot.answer_callback_query(call.id, str(e))

    # ──────────────────────────────────────────────
    # Уменьшить количество
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("cart_dec:")
    )
    def handle_cart_decrease(call: types.CallbackQuery) -> None:
        product_id = int(call.data.split(":")[1])
        chat_id = call.message.chat.id

        cart = cart_repo.get_or_create(chat_id)

        if product_id not in cart.items:
            bot.answer_callback_query(call.id, "Товар не в корзине.")
            return

        cart.remove_item(product_id)
        cart_repo.update(cart)
        bot.answer_callback_query(call.id, "➖ Удалено")
        _send_cart(chat_id, call.message.message_id)

    # ──────────────────────────────────────────────
    # Очистить корзину
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "cart:clear")
    def handle_clear_cart(call: types.CallbackQuery) -> None:
        chat_id = call.message.chat.id
        cart_repo.clear_cart(chat_id)
        bot.answer_callback_query(call.id, "🗑 Корзина очищена")
        _send_cart(chat_id, call.message.message_id)