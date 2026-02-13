"""
Notification Service — sending notifications via Telegram.

Encapsulates all notification logic:
- Notifications to the buyer about order changes
- Notifications to the seller about new orders
- Payment notifications
"""

import logging
import telebot

from domain.entities.order import Order
from utils.formatters import (
    format_order_for_customer,
    format_order_for_seller,
    format_order_status_update,
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Notification service.

    Dependency Injection: Gets the bot and seller_chat_id through the constructor.
    """

    def __init__(self, bot: telebot.TeleBot, seller_chat_id: str):
        """
        Args:
            bot: Telegram bot instance
            seller_chat_id: Merchant Chat ID
        """
        self._bot = bot
        self._seller_chat_id = seller_chat_id
        logger.info("✅ NotificationService initialized")

    def notify_order_created(self, order: Order, payment_url: str = None) -> None:
        """
        Notifies the buyer that an order has been created.

        Args:
            order: Created order
            payment_url: Payment URL (if Stripe)
        """
        try:
            text = (
                f"✅ <b>Заказ #{order.order_id} создан!</b>\n\n"
                + format_order_for_customer(order)
            )
            self._bot.send_message(order.chat_id, text, parse_mode="HTML")
        except Exception as e:
            logger.error(f"notify_order_created error: {e}")

    def notify_order_status_changed(self, order: Order) -> None:
        """
        Notifies the buyer of a change in the status of the order.

        Args:
            order: Order with updated status
        """
        try:
            self._bot.send_message(
                order.chat_id,
                format_order_status_update(order),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"notify_order_status_changed error: {e}")

    def notify_seller_new_order(
        self,
        order: Order,
        customer_name: str,
        keyboard=None,
    ) -> int:
        """
        Notifies the seller of a new order.

        Args:
            order: Order
            customer_name: Buyer's Name
            keyboard: InlineKeyboard for the message

        Returns:
            int: ID of the sent message
        """
        if not self._seller_chat_id:
            return 0

        try:
            text = format_order_for_seller(order, customer_name)
            msg = self._bot.send_message(
                self._seller_chat_id,
                text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return msg.message_id
        except Exception as e:
            logger.error(f"notify_seller_new_order error: {e}")
            return 0

    def notify_seller_payment_received(
        self,
        order: Order,
        customer_name: str,
    ) -> None:
        """
        Notifies the seller of a successful payment.

        Args:
            order: Paid order
            customer_name: Buyer's Name
        """
        if not self._seller_chat_id:
            return

        try:
            text = (
                f"💳 <b>ОПЛАТА ПОЛУЧЕНА! Заказ #{order.order_id}</b>\n\n"
                + format_order_for_seller(order, customer_name)
            )
            self._bot.send_message(
                self._seller_chat_id,
                text,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"notify_seller_payment_received error: {e}")

    def update_seller_order_status(
        self,
        order: Order,
        customer_name: str,
        stage: str = "paid",
    ) -> None:
        """
        Updates the seller's existing order message.

        Args:
        order: Order with updated status
        customer_name: Buyer's Name
        stage: Order stage for keyboard:
            - "new": new order (cash)
            - "paid": paid online, pending confirmation ✅
            - "confirmed": confirmed, awaiting delivery
        """
        if not self._seller_chat_id or not order.seller_message_id:
            logger.warning(
                f"Cannot update seller message: "
                f"seller_chat_id={self._seller_chat_id}, "
                f"seller_message_id={order.seller_message_id}"
            )
            return

        try:
            from utils.formatters import format_order_for_seller
            from presentation.keyboards.inline_keyboards import (
                get_seller_order_keyboard,
            )

            if stage == "paid":
                header = f"💳 <b>ОПЛАТА ПОЛУЧЕНА! Заказ #{order.order_id}</b>\n\n"
            else:
                header = f"🔔 <b>ЗАКАЗ #{order.order_id}</b>\n\n"

            text = header + format_order_for_seller(order, customer_name)
            keyboard = get_seller_order_keyboard(order, stage=stage)

            self._bot.edit_message_text(
                text=text,
                chat_id=self._seller_chat_id,
                message_id=order.seller_message_id,
                parse_mode="HTML",
                reply_markup=keyboard,
            )

            logger.info(
                f"✅ Updated seller message for order #{order.order_id} "
                f"(stage: {stage})"
            )

        except Exception as e:
            logger.error(f"update_seller_order_status error: {e}", exc_info=True)

    def notify_low_stock(self, product_name: str, remaining: int) -> None:
        """
        Notifies the seller that the stock is low.

        Args:
            product_name: Product Name
            remaining: Stock balance
        """
        if not self._seller_chat_id:
            return

        try:
            self._bot.send_message(
                self._seller_chat_id,
                f"⚠️ <b>Низкий остаток!</b>\n"
                f"Товар: {product_name}\n"
                f"Осталось: {remaining} шт.",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"notify_low_stock error: {e}")
