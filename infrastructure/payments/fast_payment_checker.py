"""
Fast Payment Checker - checks payment status every 3 seconds for up to 15 seconds.

Stops immediately when:
- Payment is confirmed
- User manually checks and gets success
"""

import threading
import time
import logging
from typing import Dict, Optional
from datetime import datetime

from domain.entities.order import Order

logger = logging.getLogger(__name__)


class FastPaymentChecker:
    """
    Fast payment checker that polls every 3 seconds for up to 15 seconds.
    """
    
    def __init__(self, payment_service):
        self.payment_service = payment_service
        self._active_checks: Dict[int, threading.Thread] = {}
        self._stop_events: Dict[int, threading.Event] = {}
    
    def start_check(self, order_id: int, order: Order, chat_id: int, bot) -> None:
        """
        Starts fast payment checking for an order.
        
        Args:
            order_id: Order ID to check
            order: Order object
            chat_id: User's chat ID
            bot: Telegram bot instance
        """
        self.stop_check(order_id)

        stop_event = threading.Event()
        self._stop_events[order_id] = stop_event
        
        check_thread = threading.Thread(
            target=self._check_payment_loop,
            args=(order_id, order, chat_id, bot, stop_event),
            daemon=True
        )
        self._active_checks[order_id] = check_thread
        check_thread.start()
        
        logger.info(f"🚀 Started fast payment check for order #{order_id}")
    
    def stop_check(self, order_id: int) -> None:
        """
        Stops payment checking for specific order.
        
        Args:
            order_id: Order ID to stop checking
        """
        if order_id in self._stop_events:
            self._stop_events[order_id].set()
            logger.info(f"⏹️ Stopped fast payment check for order #{order_id}")
        
        if order_id in self._active_checks:
            del self._active_checks[order_id]
        
        if order_id in self._stop_events:
            del self._stop_events[order_id]
    
    def stop_all_checks(self) -> None:
        """Stops all active payment checks."""
        for order_id in list(self._stop_events.keys()):
            self.stop_check(order_id)

    def _check_payment_loop(self, order_id: int, order: Order, chat_id: int, bot, stop_event: threading.Event) -> None:
        """
        Internal method that runs the checking loop.

        Args:
            order_id: Order ID to check
            order: Order object
            chat_id: User's chat ID
            bot: Telegram bot instance
            stop_event: Event to signal stop
        """
        start_time = time.time()
        max_duration = 300
        check_interval = 60

        while not stop_event.is_set():
            current_time = time.time()
            elapsed = current_time - start_time

            if elapsed >= max_duration:
                logger.info(f"⏰ Fast payment check timeout for order #{order_id}")
                try:
                    bot.send_message(
                        chat_id,
                        "⏰ Время автоматической проверки платежа истекло.\n"
                        "Вы можете проверить статус вручную в разделе '📦 Мои заказы'.",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Error sending timeout message: {e}")
                break

            try:
                result = self.payment_service.check_stripe_payment(order)

                if result.is_paid:
                    logger.info(f"✅ Payment confirmed via fast check for order #{order_id}")

                    try:
                        bot.send_message(
                            chat_id,
                            result.message_for_user,
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        logger.error(f"Error sending success message: {e}")

                    break

                check_number = int(elapsed / check_interval) + 1
                logger.info(
                    f"🔄 Fast payment check #{check_number}/5 for order #{order_id} - not paid yet"
                )

            except Exception as e:
                logger.error(f"Error in fast payment check for order #{order_id}: {e}")

            if stop_event.wait(check_interval):
                break

        self.stop_check(order_id)
