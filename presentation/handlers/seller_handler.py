"""
Seller panel handlers.

Access is only for SELLER_CHAT_ID.
"""

import logging
import telebot
from telebot import types

from application.services.order_service import OrderService
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.repositories.catalog_repository import CatalogRepository
from domain.enums.order_status import OrderStatus
from presentation.keyboards.inline_keyboards import get_seller_order_keyboard
from presentation.keyboards.main_keyboards import get_seller_main_keyboard
from utils.formatters import (
    format_order_for_seller,
    format_order_status_update,
)
from utils.helpers import get_customer_name

logger = logging.getLogger(__name__)


def register_seller_handlers(
    bot: telebot.TeleBot,
    order_service: OrderService,
    order_repo: OrderRepository,
    seller_chat_id: str,
    catalog_repo: CatalogRepository,
) -> None:
    """
    Registers seller panel handlers.

    Args:
        bot: Bot instance
        order_service: Order Service
        order_repo: Order Repository
        seller_chat_id: Merchant Chat ID
        catalog_repo: Directory Repository
    """

    def is_seller(chat_id: int) -> bool:
        """Verifies that the user is a seller."""
        return str(chat_id) == str(seller_chat_id)

    # ──────────────────────────────────────────────
    # command /seller
    # ──────────────────────────────────────────────

    @bot.message_handler(commands=["seller"])
    def handle_seller_panel(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            bot.send_message(message.chat.id, "⛔ Доступ запрещён.")
            return

        bot.send_message(
            message.chat.id,
            "👨‍💼 <b>Панель продавца</b>",
            parse_mode="HTML",
            reply_markup=get_seller_main_keyboard(),
        )

    # ──────────────────────────────────────────────
    # Active Orders
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "📋 Активные заказы")
    def handle_active_orders(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        active = [
            o for o in order_repo.get_all()
            if not o.is_final()
        ]

        if not active:
            bot.send_message(message.chat.id, "Нет активных заказов.")
            return

        for order in active:
            customer_name = get_customer_name(bot, order.chat_id)
            text = format_order_for_seller(order, customer_name)
            stage = "confirmed" if order.status == OrderStatus.CONFIRMED else "new"
            bot.send_message(
                message.chat.id,
                text,
                parse_mode="HTML",
                reply_markup=get_seller_order_keyboard(order, stage=stage),
            )

    # ──────────────────────────────────────────────
    # Completed orders
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "✅ Выполненные")
    def handle_delivered_orders(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        delivered = order_repo.get_by_status(OrderStatus.DELIVERED)
        if not delivered:
            bot.send_message(message.chat.id, "Нет выполненных заказов.")
            return

        lines = [f"✅ <b>Выполненные заказы: {len(delivered)}</b>\n"]
        for order in delivered[-10:]:
            lines.append(
                f"#{order.order_id} | "
                f"{order.total_amount}₴ | "
                f"{order.created_at.strftime('%d.%m %H:%M')}"
            )

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

    # ──────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "📊 Статистика")
    def handle_statistics(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        all_orders = order_repo.get_all()
        total = len(all_orders)
        delivered = len(order_repo.get_by_status(OrderStatus.DELIVERED))
        cancelled = len(order_repo.get_by_status(OrderStatus.CANCELLED))
        pending = len([o for o in all_orders if not o.is_final()])

        total_revenue = sum(
            o.total_amount
            for o in order_repo.get_by_status(OrderStatus.DELIVERED)
        )

        text = (
            f"📊 <b>Статистика магазина</b>\n\n"
            f"📦 Всего заказов: {total}\n"
            f"✅ Выполнено: {delivered}\n"
            f"❌ Отменено: {cancelled}\n"
            f"⏳ В обработке: {pending}\n\n"
            f"💰 Выручка: {total_revenue:.2f}₴"
        )

        bot.send_message(message.chat.id, text, parse_mode="HTML")

    # ──────────────────────────────────────────────
    # Little in stock
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "⚠️ Мало на складе")
    def handle_low_stock(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        low_stock = catalog_repo.get_low_stock_products(threshold=5)
        if not low_stock:
            bot.send_message(message.chat.id, "✅ Все товары в норме!")
            return

        lines = [f"⚠️ <b>Товары с низким остатком:</b>\n"]
        for product in low_stock:
            lines.append(f"• {product.name} — {product.stock} шт.")

        bot.send_message(
            message.chat.id,
            "\n".join(lines),
            parse_mode="HTML",
        )

    # ──────────────────────────────────────────────
    # Updating the catalog by the seller
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "🔄 Обновить каталог")
    def handle_seller_reload(message: types.Message) -> None:
        if not is_seller(message.chat.id):
            return

        try:
            catalog_repo.reload()
            bot.send_message(message.chat.id, "✅ Каталог обновлён!")
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

    # ──────────────────────────────────────────────
    # Order confirmation
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_confirm:")
    )
    def handle_confirm_order(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.confirm_order(order_id)
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=format_order_for_seller(order, customer_name),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=get_seller_order_keyboard(order, stage="confirmed"),
            )

            bot.answer_callback_query(call.id, "✅ Заказ подтверждён!")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Confirm order error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка подтверждения.")

    # ──────────────────────────────────────────────
    # Delivered
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_deliver:")
    )
    def handle_deliver_order(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.mark_as_delivered(order_id)
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=(
                    f"🚚 <b>ЗАКАЗ #{order_id} ДОСТАВЛЕН</b>\n\n"
                    + format_order_for_seller(order, customer_name)
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=None,
            )

            bot.answer_callback_query(call.id, "🚚 Заказ доставлен! Товары списаны.")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Deliver order error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка.")

    # ──────────────────────────────────────────────
    # Cancellation by the seller
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("seller_cancel:")
    )
    def handle_seller_cancel(call: types.CallbackQuery) -> None:
        if not is_seller(call.message.chat.id):
            bot.answer_callback_query(call.id, "⛔ Нет доступа.")
            return

        order_id = int(call.data.split(":")[1])

        try:
            order = order_service.cancel_order(
                order_id, reason="Отменён менеджером"
            )
            customer_name = get_customer_name(bot, order.chat_id)

            bot.edit_message_text(
                text=(
                    f"❌ <b>ЗАКАЗ #{order_id} ОТМЕНЁН</b>\n\n"
                    + format_order_for_seller(order, customer_name)
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=None,
            )

            bot.answer_callback_query(call.id, "❌ Заказ отменён.")

            bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )

        except Exception as e:
            logger.error(f"Seller cancel error: {e}")
            bot.answer_callback_query(call.id, "❌ Ошибка отмены.")
