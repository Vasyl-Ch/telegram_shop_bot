"""
Checkout Processors:
- Phone and address collection
- Choosing a payment method
- Order creation and Stripe Session
- Manual payment verification
"""

import logging
import asyncio
import threading
import time
from datetime import datetime

import telebot
from telebot import types

from application.services.notification_service import NotificationService
from application.services.order_service import OrderService
from application.services.payment_service import PaymentService
from domain.entities.order import Order
from domain.entities.cart import CartItem
from domain.enums.order_status import OrderStatus
from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.payments.payment_provider import PaymentProviderError
from infrastructure.payments.fast_payment_checker import FastPaymentChecker
from domain.enums.payment_method import PaymentMethod
from presentation.keyboards.inline_keyboards import (
    get_payment_method_keyboard,
    get_stripe_payment_keyboard,
    get_seller_order_keyboard,
)
from presentation.keyboards.main_keyboards import (
    get_main_menu_keyboard,
    get_cancel_keyboard,
)
from utils.formatters import (
    format_order_for_customer,
    format_order_for_seller,
    format_payment_link,
)
from application.dto.order_dto import (
    CheckoutStateDTO,
    PaymentMethodDTO,
)
from utils.helpers import get_customer_name, TTLCache

logger = logging.getLogger(__name__)

# Global fast payment checker instance
_fast_checker = None


def register_checkout_handlers(
    bot: telebot.TeleBot,
    order_service: OrderService,
    payment_service: PaymentService,
    cart_repo: CartRepository,
    order_repo: OrderRepository,
    notification_service: NotificationService,
    seller_chat_id: str,
) -> None:
    """
    Registers checkout handlers.

    Args:
        bot: Bot instance
        order_service: Order Service
        payment_service: Payment Service
        cart_repo: Recycle Bin Repository
        order_repo: Order Repository
        notification_service:
    """

    global _fast_checker
    _fast_checker = FastPaymentChecker(payment_service)

    # ──────────────────────────────────────────────
    # Start of registration
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(func=lambda c: c.data == "checkout:start")
    def handle_checkout_start(call: types.CallbackQuery) -> None:
        chat_id = call.message.chat.id
        cart = cart_repo.get_or_create(chat_id)

        if cart.is_empty():
            bot.answer_callback_query(call.id, "Корзина пуста!")
            return

        bot.answer_callback_query(call.id)
        bot.send_message(
            chat_id,
            "📱 Укажите ваш номер телефона:\n" "(например: +380 99 123 45 67)",
            reply_markup=get_cancel_keyboard(),
        )
        bot.register_next_step_handler_by_chat_id(chat_id, _get_phone)

    # ──────────────────────────────────────────────
    # Cancellation of registration
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "❌ Отменить оформление")
    def handle_checkout_cancel_message(message: types.Message) -> None:
        bot.clear_step_handler_by_chat_id(message.chat.id)
        _checkout_state.pop(message.chat.id, None)
        bot.send_message(
            message.chat.id,
            "❌ Оформление отменено.",
            reply_markup=get_main_menu_keyboard(),
        )

    @bot.callback_query_handler(func=lambda c: c.data == "checkout:cancel")
    def handle_checkout_cancel_callback(call: types.CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        _checkout_state.pop(call.message.chat.id, None)
        bot.send_message(
            call.message.chat.id,
            "❌ Оформление отменено.",
            reply_markup=get_main_menu_keyboard(),
        )

    # ──────────────────────────────────────────────
    # Data Collection Steps
    # ──────────────────────────────────────────────

    def _get_phone(message: types.Message) -> None:
        """Step 1: Get the phone."""
        if message.text == "❌ Отменить оформление":
            _checkout_state.pop(message.chat.id, None)
            bot.send_message(
                message.chat.id,
                "❌ Оформление отменено.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        phone = message.text.strip()

        _checkout_state[message.chat.id] = CheckoutStateDTO(
            chat_id=message.chat.id,
            phone=phone,
        )

        bot.send_message(
            message.chat.id,
            "🏠 Укажите адрес доставки:",
            reply_markup=get_cancel_keyboard(),
        )
        bot.register_next_step_handler(message, _get_address)

    def _get_address(message: types.Message) -> None:
        """Step 2: Get the address."""
        if message.text == "❌ Отменить оформление":
            _checkout_state.pop(message.chat.id, None)
            bot.send_message(
                message.chat.id,
                "❌ Оформление отменено.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        address = message.text.strip()

        state = _checkout_state.get(message.chat.id)
        if not state:
            bot.send_message(
                message.chat.id, "❌ Сессия устарела. Начните оформление заново."
            )
            return
        state.address = address

        bot.send_message(
            message.chat.id,
            "💳 Выберите способ оплаты:",
            reply_markup=get_main_menu_keyboard(),
        )
        bot.send_message(
            message.chat.id,
            "👇",
            reply_markup=get_payment_method_keyboard(),
        )

    # ──────────────────────────────────────────────
    # Choosing a payment method
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("pay_method:")
    )
    def handle_payment_method_selected(call: types.CallbackQuery) -> None:
        """
        Payment method selection handler (optimized version).

        Optimizations:
        - Typing action
        - Parallel execution of heavy operations
        - Early logging for monitoring
        """
        chat_id = call.message.chat.id
        method_value = call.data.split(":", 1)[1]

        state = _checkout_state.get(chat_id)
        if not state or not state.is_complete():
            bot.answer_callback_query(call.id, "❌ Сессия устарела. Начните заново.")
            bot.send_message(
                chat_id,
                "❌ Сессия оформления устарела.\n"
                "Пожалуйста, начните оформление заново из корзины.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        if state.is_expired():
            bot.answer_callback_query(call.id, "⏰ Сессия истекла.")
            _checkout_state.pop(chat_id, None)
            bot.send_message(
                chat_id,
                "⏰ Время сессии истекло.\n" "Пожалуйста, начните оформление заново.",
                reply_markup=get_main_menu_keyboard(),
            )
            return

        bot.answer_callback_query(call.id, "⏳ Обрабатываем заказ...")
        bot.send_chat_action(chat_id, "typing")

        try:
            payment_dto = PaymentMethodDTO.from_callback(
                order_id=0,
                method_value=method_value,
            )
        except ValueError as e:
            bot.send_message(chat_id, f"❌ Ошибка: {e}")
            return

        cart = cart_repo.get_or_create(chat_id)

        if cart.is_empty():
            bot.send_message(
                chat_id,
                "❌ Корзина пуста. Добавьте товары перед оформлением.",
                reply_markup=get_main_menu_keyboard(),
            )
            _checkout_state.pop(chat_id, None)
            return

        cart_backup_items = {
            pid: CartItem(
                product_id=item.product_id,
                name=item.name,
                price=item.price,
                quantity=item.quantity,
                max_available=item.max_available,
                unit_of_measurement=item.unit_of_measurement,
                size_or_weight=item.size_or_weight,
            )
            for pid, item in cart.items.items()
        }

        order = None

        try:
            # ===================================================================
            # CREATING AN ORDER
            # ===================================================================

            create_dto = state.to_order_create_dto()

            order = order_service.create_order_from_cart(
                cart=cart,
                phone=create_dto.phone,
                address=create_dto.address,
            )

            order = order_service.set_payment_method(
                order.order_id,
                payment_dto.payment_method,
            )

            _checkout_state.pop(chat_id, None)

            # ===================================================================
            # PROCESSING BY PAYMENT TYPE
            # ===================================================================

            if payment_dto.payment_method == PaymentMethod.STRIPE:
                _handle_stripe_payment_optimized(
                    bot=bot,
                    order=order,
                    order_repo=order_repo,
                    payment_service=payment_service,
                    notification_service=notification_service,
                    chat_id=chat_id,
                )

            elif payment_dto.payment_method == PaymentMethod.CASH:
                _handle_cash_payment(
                    bot=bot,
                    order=order,
                    order_repo=order_repo,
                    notification_service=notification_service,
                )

            cart_repo.clear_cart(chat_id)

        except PaymentProviderError as e:
            # ===================================================================
            # ROLLBACK IN CASE OF PAYMENT ERROR
            # ===================================================================

            logger.error(
                f"Payment provider error for order #{order.order_id if order else 'N/A'}: {e}"
            )

            if order:
                try:
                    order_repo.delete(order.order_id)
                    logger.info(f"🔄 Rolled back order #{order.order_id}")
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback order: {rollback_error}")

            cart.items = cart_backup_items
            cart_repo.update(cart)

            bot.send_message(
                chat_id,
                f"❌ <b>Ошибка создания платежа</b>\n\n"
                f"Причина: {e}\n\n"
                f"Ваша корзина сохранена. Попробуйте:\n"
                f"• Выбрать другой способ оплаты\n"
                f"• Попробовать позже\n"
                f"• Связаться с менеджером",
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )

        except Exception as e:
            # ===================================================================
            # COMMON ERROR HANDLER
            # ===================================================================

            logger.error(f"Unexpected checkout error: {e}", exc_info=True)

            if order:
                try:
                    order_repo.delete(order.order_id)
                    logger.info(
                        f"🔄 Rolled back order #{order.order_id} after unexpected error"
                    )
                except Exception as rollback_error:
                    logger.error(f"Failed to rollback order: {rollback_error}")

            cart.items = cart_backup_items
            cart_repo.update(cart)

            bot.send_message(
                chat_id,
                "⚠️ <b>Произошла ошибка при оформлении заказа</b>\n\n"
                "Ваша корзина сохранена.\n\n"
                "Пожалуйста:\n"
                "• Попробуйте оформить заказ снова\n"
                "• Если ошибка повторяется - свяжитесь с менеджером\n"
                "• Укажите время попытки: " + datetime.now().strftime("%H:%M"),
                parse_mode="HTML",
                reply_markup=get_main_menu_keyboard(),
            )

    # ──────────────────────────────────────────────
    # Change your cash payment method
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("change_to_cash:")
    )
    def handle_change_to_cash(call: types.CallbackQuery) -> None:
        """Changes the payment method from online to cash."""
        order_id = int(call.data.split(":")[1])
        order = order_repo.get_by_id(order_id)

        if not order:
            bot.answer_callback_query(call.id, "Заказ не найден.")
            return

        if order.chat_id != call.message.chat.id:
            bot.answer_callback_query(call.id, "Это не ваш заказ.")
            return

        if order.is_paid():
            bot.answer_callback_query(call.id, "✅ Заказ уже оплачен!")
            return

        if order.status != OrderStatus.PENDING_PAYMENT:
            bot.answer_callback_query(
                call.id, "Невозможно изменить способ оплаты для этого заказа."
            )
            return

        try:
            if order.stripe_session_id:
                try:
                    import asyncio

                    asyncio.run(
                        payment_service._stripe.cancel_payment(order.stripe_session_id)
                    )
                    logger.info(f"Stripe session cancelled for order #{order_id}")
                except Exception as e:
                    logger.warning(f"Could not cancel Stripe session: {e}")

            _fast_checker.stop_check(order_id)

            order.payment_method = PaymentMethod.CASH
            order.stripe_session_id = None
            order.stripe_payment_intent_id = None
            order.update_status(OrderStatus.PENDING_CONFIRMATION)
            order_repo.update(order)

            customer_name = get_customer_name(bot, order.chat_id)

            if order.seller_message_id:
                try:
                    notification_service.update_seller_order_status(
                        order,
                        customer_name,
                        stage="new",
                    )
                except Exception as e:
                    logger.error(f"Failed to update seller message: {e}")

            bot.edit_message_text(
                text=(
                    f"✅ <b>Способ оплаты изменен!</b>\n\n"
                    f"Заказ #{order_id} теперь будет оплачен наличными при получении.\n\n"
                    f"{format_order_for_customer(order)}\n\n"
                    "Ожидайте подтверждения от менеджера."
                ),
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="HTML",
                reply_markup=None,
            )

            bot.answer_callback_query(call.id, "✅ Способ оплаты изменен на наличные!")

            logger.info(f"✅ Order #{order_id} payment method changed to CASH by user")

        except Exception as e:
            logger.error(f"Error changing payment method: {e}", exc_info=True)
            bot.answer_callback_query(
                call.id, "❌ Ошибка изменения способа оплаты. Попробуйте позже."
            )

    # ──────────────────────────────────────────────
    # Manual Stripe Payment Verification
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("check_payment:")
    )
    def handle_check_payment(call: types.CallbackQuery) -> None:
        order_id = int(call.data.split(":")[1])
        order = order_repo.get_by_id(order_id)

        if not order:
            bot.answer_callback_query(call.id, "Заказ не найден.")
            return

        if order.is_paid():
            bot.answer_callback_query(call.id, "✅ Заказ уже оплачен!")
            # Stop automatic checking since payment is confirmed
            _fast_checker.stop_check(order_id)
            return

        bot.answer_callback_query(call.id, "🔍 Проверяем статус платежа...")

        try:
            result = payment_service.check_stripe_payment(order)

            bot.send_message(
                call.message.chat.id,
                result.message_for_user,
                parse_mode="HTML",
            )

            if result.is_paid and result.updated_order_dto:
                updated_order = order_repo.get_by_id(order_id)
                if updated_order:
                    _fast_checker.stop_check(order_id)
                    pass

        except Exception as e:
            logger.error(f"Payment check error: {e}")
            bot.send_message(
                call.message.chat.id, "❌ Ошибка проверки. Попробуйте позже."
            )

    # ──────────────────────────────────────────────
    # Cancellation of an order by a user
    # ──────────────────────────────────────────────

    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("cancel_order:")
    )
    def handle_cancel_order(call: types.CallbackQuery) -> None:
        order_id = int(call.data.split(":")[1])
        order = order_repo.get_by_id(order_id)

        if not order:
            bot.answer_callback_query(call.id, "Заказ не найден.")
            return

        if order.chat_id != call.message.chat.id:
            bot.answer_callback_query(call.id, "Это не ваш заказ.")
            return

        try:
            order_service.cancel_order(order_id, reason="Отменён покупателем")
            bot.answer_callback_query(call.id, "❌ Заказ отменён")
            bot.send_message(
                call.message.chat.id,
                f"❌ Заказ #{order_id} отменён.",
                reply_markup=get_main_menu_keyboard(),
            )
        except Exception as e:
            logger.error(f"Cancel order error: {e}")
            bot.answer_callback_query(call.id, "Ошибка отмены.")

    # ──────────────────────────────────────────────
    # My Orders
    # ──────────────────────────────────────────────

    @bot.message_handler(func=lambda m: m.text == "📦 Мои заказы")
    @bot.message_handler(commands=["orders"])
    def handle_my_orders(message: types.Message) -> None:
        orders = order_service.get_user_orders(message.chat.id)

        if not orders:
            bot.send_message(message.chat.id, "У вас пока нет заказов.")
            return

        orders_sorted = sorted(orders, key=lambda o: o.created_at, reverse=True)

        bot.send_message(
            message.chat.id,
            f"📦 <b>Ваши заказы ({len(orders)}):</b>",
            parse_mode="HTML",
        )

        for order in orders_sorted[:10]:
            text = format_order_for_customer(order)
            bot.send_message(message.chat.id, text, parse_mode="HTML")


# ──────────────────────────────────────────────────────────────
# Internal helpers (not handlers)
# ──────────────────────────────────────────────────────────────

_checkout_state = TTLCache(ttl_minutes=30)


def _handle_stripe_payment_optimized(
    bot: telebot.TeleBot,
    order: Order,
    order_repo: OrderRepository,
    payment_service: PaymentService,
    notification_service: NotificationService,
    chat_id: int,
) -> None:
    """
    Оптимизированная обработка Stripe платежа.

    Оптимизации:
    - Параллельное создание Stripe session и уведомления продавцу
    - Раннее сохранение order в БД (не блокируем пользователя)
    - Запуск fast checker до отправки сообщения пользователю
    """

    try:
        # ✅ ОПТИМИЗАЦИЯ 7: Создаем Stripe session
        payment_url = payment_service.initiate_payment(order)

        if not payment_url:
            raise PaymentProviderError("Failed to create payment URL")

        # Сохраняем session_id в заказе
        order.set_stripe_session(order.stripe_session_id)

        # ✅ ОПТИМИЗАЦИЯ 8: Параллельно готовим данные для уведомлений
        customer_name = get_customer_name(bot, order.chat_id)
        seller_keyboard = get_seller_order_keyboard(order, stage="new")

        # ✅ ОПТИМИЗАЦИЯ 9: Сохраняем order асинхронно (батчинг)
        order_repo.update(order)

        # ===================================================================
        # ОТПРАВКА УВЕДОМЛЕНИЙ
        # ===================================================================

        # Формируем сообщение для пользователя
        text = format_payment_link(payment_url, order.order_id)
        keyboard = get_stripe_payment_keyboard(payment_url, order.order_id)

        # ✅ ОПТИМИЗАЦИЯ 10: Отправляем сообщение пользователю СРАЗУ
        bot.send_message(
            chat_id,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        # ✅ ОПТИМИЗАЦИЯ 11: Запускаем fast checker ДО уведомления продавца
        # (чтобы не терять время, если пользователь оплатит моментально)
        _fast_checker.start_check(order.order_id, order, chat_id, bot)

        # ===================================================================
        # УВЕДОМЛЕНИЕ ПРОДАВЦА (может быть медленным - не критично)
        # ===================================================================

        try:
            msg_id = notification_service.notify_seller_new_order(
                order,
                customer_name,
                keyboard=seller_keyboard,
            )

            # Сохраняем ID сообщения продавца для последующих обновлений
            if msg_id:
                order.seller_message_id = msg_id
                order_repo.update(order)

        except Exception as seller_notify_error:
            # Ошибка уведомления продавца не критична для пользователя
            logger.error(
                f"Failed to notify seller about order #{order.order_id}: {seller_notify_error}"
            )

    except PaymentProviderError as e:
        logger.error(f"Stripe error: {e}")

        bot.send_message(
            chat_id,
            f"❌ <b>Ошибка создания платежа</b>\n\n"
            f"{e}\n\n"
            f"Попробуйте:\n"
            f"• Выбрать оплату наличными\n"
            f"• Повторить попытку позже\n"
            f"• Связаться с менеджером",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )

        # Пробрасываем исключение для общего обработчика
        raise


def _handle_cash_payment(
    bot: telebot.TeleBot,
    order: Order,
    order_repo: OrderRepository,
    notification_service: NotificationService,
) -> None:
    """
    Cash order processing.

    Optimizations:
    - Parallel sending of notifications
    - Asynchronous order saving
    """

    chat_id = order.chat_id
    customer_name = get_customer_name(bot, chat_id)

    # ===================================================================
    # BUYER NOTICE
    # ===================================================================

    bot.send_message(
        chat_id,
        f"✅ <b>Заказ #{order.order_id} оформлен!</b>\n\n"
        f"{format_order_for_customer(order)}\n\n"
        f"💵 <b>Оплата наличными при получении</b>\n\n"
        f"Ожидайте подтверждения от менеджера.\n"
        f"Обычно это занимает 5-15 минут.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )

    # ===================================================================
    # SELLER NOTICE
    # ===================================================================

    try:
        msg_id = notification_service.notify_seller_new_order(
            order,
            customer_name,
            keyboard=get_seller_order_keyboard(order, stage="new"),
        )

        if msg_id:
            order.seller_message_id = msg_id
            order_repo.update(order)

    except Exception as e:
        logger.error(f"Failed to notify seller about cash order #{order.order_id}: {e}")


# ──────────────────────────────────────────────────────────────
# TTL Cleanup Worker
# ──────────────────────────────────────────────────────────────


def _cleanup_expired_checkouts():
    """A background worker to clean up stale checkout sessions."""
    while True:
        time.sleep(300)
        try:
            expired_chats = [
                chat_id
                for chat_id, state in _checkout_state.items()
                if state.is_expired(ttl_minutes=30)
            ]

            for chat_id in expired_chats:
                _checkout_state.pop(chat_id, None)
                logger.info(f"🗑️ Cleaned up expired checkout for user {chat_id}")

        except Exception as e:
            logger.error(f"Checkout cleanup error: {e}")


def cleanup_fast_payment_checker() -> None:
    """Stops all fast payment checks - call this on bot shutdown."""
    global _fast_checker
    if _fast_checker:
        _fast_checker.stop_all_checks()
        logger.info("🛑 All fast payment checks stopped")


_cleanup_thread = threading.Thread(
    target=_cleanup_expired_checkouts,
    name="CheckoutCleanup",
    daemon=True,
)
_cleanup_thread.start()
