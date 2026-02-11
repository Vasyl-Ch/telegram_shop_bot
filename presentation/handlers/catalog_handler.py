"""
Catalog processors: categories, products, search.
"""

import logging
import telebot
from telebot import types

from infrastructure.repositories.catalog_repository import CatalogRepository
from infrastructure.repositories.cart_repository import CartRepository
from domain.entities.cart import CartItem
from presentation.keyboards.inline_keyboards import (
    get_categories_keyboard,
    get_products_keyboard,
    get_product_detail_keyboard,
)
from utils.formatters import format_product_card

logger = logging.getLogger(__name__)


def register_catalog_handlers(
    bot: telebot.TeleBot,
    catalog_repo: CatalogRepository,
    cart_repo: CartRepository,
) -> None:
    """
    Registers directory handlers.

    Args:
        bot: Bot instance
        catalog_repo: Directory Repository
        cart_repo: Recycle Bin Repository
    """

    # ──────────────────────────────────────────────
    # Category
    # ──────────────────────────────────────────────

    @bot.message_handler(
        func=lambda m: m.text in ("🗂 Категории",)
    )
    @bot.message_handler(commands=["categories"])
    def handle_categories(message: types.Message) -> None:
        categories = catalog_repo.get_categories()
        if not categories:
            bot.send_message(message.chat.id, "Категории не найдены.")
            return

        bot.send_message(
            message.chat.id,
            "🗂 <b>Выберите категорию:</b>",
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(categories),
        )

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("cat:")
    )
    def handle_category_selected(call: types.CallbackQuery) -> None:
        category = call.data.split(":", 1)[1]
        products = catalog_repo.get_by_category(category)

        if not products:
            bot.answer_callback_query(call.id, "В этой категории нет товаров.")
            return

        try:
            bot.edit_message_text(
                text=f"📂 <b>Категория: {category}</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_products_keyboard(products, category),
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                f"📂 <b>Категория: {category}</b>",
                parse_mode="HTML",
                reply_markup=get_products_keyboard(products, category),
            )

        bot.answer_callback_query(call.id)

    @bot.callback_query_handler(func=lambda c: c.data == "back:categories")
    def handle_back_to_categories(call: types.CallbackQuery) -> None:
        categories = catalog_repo.get_categories()
        try:
            bot.edit_message_text(
                text="🗂 <b>Выберите категорию:</b>",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_categories_keyboard(categories),
            )
        except Exception:
            bot.send_message(
                call.message.chat.id,
                "🗂 <b>Выберите категорию:</b>",
                parse_mode="HTML",
                reply_markup=get_categories_keyboard(categories),
            )
        bot.answer_callback_query(call.id)

    # ──────────────────────────────────────────────
    # Full catalog
    # ──────────────────────────────────────────────

    @bot.message_handler(
        func=lambda m: m.text in ("📋 Каталог",)
    )
    @bot.message_handler(commands=["catalog"])
    def handle_full_catalog(message: types.Message) -> None:
        categories = catalog_repo.get_categories()
        if not categories:
            bot.send_message(message.chat.id, "Каталог пуст.")
            return

        bot.send_message(
            message.chat.id,
            "📋 <b>Каталог товаров</b>\n\nВыберите категорию:",
            parse_mode="HTML",
            reply_markup=get_categories_keyboard(categories),
        )

    # ──────────────────────────────────────────────
    # Detailed product card
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("prod:")
    )
    def handle_product_detail(call: types.CallbackQuery) -> None:
        product_id = int(call.data.split(":")[1])
        product = catalog_repo.get_by_id(product_id)

        if not product:
            bot.answer_callback_query(call.id, "Товар не найден.")
            return

        text = format_product_card(product)
        keyboard = get_product_detail_keyboard(product, product.category)

        if product.image_url:
            try:
                bot.send_photo(
                    call.message.chat.id,
                    product.image_url,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
            except Exception:
                bot.send_message(
                    call.message.chat.id,
                    text,
                    parse_mode="HTML",
                    reply_markup=keyboard,
                )
        else:
            bot.send_message(
                call.message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

        bot.answer_callback_query(call.id)

    # ──────────────────────────────────────────────
    # Add to cart
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("add:")
    )
    def handle_add_to_cart(call: types.CallbackQuery) -> None:
        product_id = int(call.data.split(":")[1])
        chat_id = call.message.chat.id

        product = catalog_repo.get_by_id(product_id)
        if not product:
            bot.answer_callback_query(call.id, "Товар не найден.")
            return

        if not product.is_available:
            bot.answer_callback_query(call.id, "Товар закончился 😔")
            return

        cart = cart_repo.get_or_create(chat_id)
        current_qty = (
            cart.items[product_id].quantity
            if product_id in cart.items
            else 0
        )

        if current_qty >= product.stock:
            bot.answer_callback_query(
                call.id,
                f"Нельзя добавить больше {product.stock} шт."
            )
            return

        try:
            cart_item = CartItem(
                product_id=product.product_id,
                name=product.name,
                price=product.price,
                quantity=1,
                max_available=product.stock,
            )
            cart.add_item(cart_item)
            cart_repo.update(cart)

            new_qty = cart.items[product_id].quantity
            bot.answer_callback_query(
                call.id,
                f"✅ {product.name} добавлен! В корзине: {new_qty} шт."
            )
        except ValueError as e:
            bot.answer_callback_query(call.id, str(e))

    # ──────────────────────────────────────────────
    # Search
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🔍 Поиск")
    def handle_search_start(message: types.Message) -> None:
        bot.send_message(
            message.chat.id,
            "🔍 Введите название товара для поиска:"
        )
        bot.register_next_step_handler(message, _process_search)

    def _process_search(message: types.Message) -> None:
        query = message.text.strip()
        if len(query) < 2:
            bot.send_message(
                message.chat.id,
                "Запрос слишком короткий. Введите хотя бы 2 символа."
            )
            return

        results = catalog_repo.search(query)
        if not results:
            bot.send_message(
                message.chat.id,
                f"По запросу «{query}» ничего не найдено."
            )
            return

        from presentation.keyboards.inline_keyboards import get_products_keyboard
        bot.send_message(
            message.chat.id,
            f"🔍 Результаты поиска «{query}»:",
            reply_markup=get_products_keyboard(results, "search"),
        )

    # ──────────────────────────────────────────────
    # Plug for "noop" buttons
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "noop")
    def handle_noop(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id, "Товар временно отсутствует")

    # ──────────────────────────────────────────────
    # Catalog update
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🔄 Обновить")
    @bot.message_handler(commands=["reload"])
    def handle_reload(message: types.Message) -> None:
        try:
            catalog_repo.reload()
            bot.send_message(message.chat.id, "✅ Каталог обновлён!")
        except Exception as e:
            logger.error(f"Reload error: {e}")
            bot.send_message(message.chat.id, "❌ Ошибка обновления каталога.")