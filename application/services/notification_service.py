"""
Notification Service — отправка уведомлений через Telegram.

Инкапсулирует всю логику уведомлений:
- Уведомления покупателю об изменениях заказа
- Уведомления продавцу о новых заказах
- Уведомления об оплате
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
    Сервис уведомлений.

    Dependency Injection: получает bot и seller_chat_id через конструктор.
    """

    def __init__(self, bot: telebot.TeleBot, seller_chat_id: str):
        """
        Args:
            bot: Инстанс Telegram бота
            seller_chat_id: ID чата продавца
        """
        self._bot = bot
        self._seller_chat_id = seller_chat_id
        logger.info("✅ NotificationService initialized")

    def notify_order_created(self, order: Order, payment_url: str = None) -> None:
        """
        Уведомляет покупателя о создании заказа.

        Args:
            order: Созданный заказ
            payment_url: URL для оплаты (если Stripe)
        """
        try:
            text = (
                f"✅ <b>Заказ #{order.order_id} создан!</b>\n\n"
                + format_order_for_customer(order)
            )
            self._bot.send_message(
                order.chat_id,
                text,
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"notify_order_created error: {e}")

    def notify_order_status_changed(self, order: Order) -> None:
        """
        Уведомляет покупателя об изменении статуса заказа.

        Args:
            order: Заказ с обновлённым статусом
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
        Уведомляет продавца о новом заказе.

        Args:
            order: Заказ
            customer_name: Имя покупателя
            keyboard: InlineKeyboard для сообщения

        Returns:
            int: ID отправленного сообщения
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
        Уведомляет продавца об успешной оплате.

        Args:
            order: Оплаченный заказ
            customer_name: Имя покупателя
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

    def notify_low_stock(self, product_name: str, remaining: int) -> None:
        """
        Уведомляет продавца о низком остатке товара.

        Args:
            product_name: Название товара
            remaining: Остаток на складе
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