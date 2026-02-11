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

import telebot
from telebot import types

from application.services.order_service import OrderService
from application.services.payment_service import PaymentService
from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.order_repository import OrderRepository
from infrastructure.payments.payment_provider import PaymentProviderError
from domain.enums.payment_method import PaymentMethod
from presentation.keyboards.inline_keyboards import (
    get_payment_method_keyboard,
    get_stripe_payment_keyboard,
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


def register_checkout_handlers(
    bot: telebot.TeleBot,
    order_service: OrderService,
    payment_service: PaymentService,
    cart_repo: CartRepository,
    order_repo: OrderRepository,
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
        stripe_provider: Stripe provider
        seller_chat_id: Merchant Chat ID
    """

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
        if len(phone) < 10:
            bot.send_message(
                message.chat.id,
                "❌ Некорректный номер. Попробуйте снова:",
                reply_markup=get_cancel_keyboard(),
            )
            bot.register_next_step_handler(message, _get_phone)
            return

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
        if len(address) < 10:
            bot.send_message(
                message.chat.id,
                "❌ Адрес слишком короткий. Укажите полный адрес:",
                reply_markup=get_cancel_keyboard(),
            )
            bot.register_next_step_handler(message, _get_address)
            return

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
    @bot.callback_query_handler(
        func=lambda c: c.data and c.data.startswith("pay_method:")
    )
    def handle_payment_method_selected(call: types.CallbackQuery) -> None:
        chat_id = call.message.chat.id
        method_value = call.data.split(":", 1)[1]

        state = _checkout_state.get(chat_id)
        if not state or not state.is_complete():
            bot.answer_callback_query(call.id, "Сессия устарела. Начните заново.")
            return

        if state.is_expired():
            _checkout_state.pop(chat_id, None)
            bot.answer_callback_query(call.id, "Сессия истекла. Начните заново.")
            return

        try:
            payment_dto = PaymentMethodDTO.from_callback(
                order_id=0,
                method_value=method_value,
            )
        except ValueError as e:
            bot.answer_callback_query(call.id, str(e))
            return

        cart = cart_repo.get_or_create(chat_id)
        cart_backup = cart_repo.get_or_create(chat_id)  # Копия

        order = None
        try:
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

            if payment_dto.payment_method == PaymentMethod.STRIPE:
                _handle_stripe_payment(
                    bot, order, order_repo, payment_service, seller_chat_id
                )
            elif payment_dto.payment_method == PaymentMethod.CASH:
                _handle_cash_payment(bot, order, order_repo, seller_chat_id)

            cart_repo.clear_cart(chat_id)

        except PaymentProviderError as e:
            if order:
                order_repo.delete(order.order_id)
                logger.error(f"Payment failed, order #{order.order_id} rolled back")

            cart_repo.update(cart_backup)

            bot.send_message(
                chat_id,
                f"❌ Ошибка создания платежа: {e}\n"
                "Ваша корзина сохранена. Попробуйте снова.",
            )
        except Exception as e:
            logger.error(f"Checkout error: {e}", exc_info=True)

            if order:
                order_repo.delete(order.order_id)
            cart_repo.update(cart_backup)

            bot.send_message(
                chat_id,
                f"⚠️ Произошла ошибка. Попробуйте позже.\n"
                "Ваша корзина сохранена.\n"
                "Если нужна помощь свяжитесь с менеджером.",
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
                    _notify_seller_paid(bot, updated_order, order_repo, seller_chat_id)

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


def _handle_stripe_payment(
    bot: telebot.TeleBot,
    order,
    order_repo: OrderRepository,
    payment_service: PaymentService,
    seller_chat_id: str,
) -> None:
    """Handles the creation of a Stripe Checkout Session."""
    try:
        payment_url = payment_service.initiate_payment(order)
        if not payment_url:
            raise PaymentProviderError("Failed to create payment URL")

        payment_data = {
            "payment_url": payment_url,
            "payment_id": order.stripe_session_id,
        }
        order.set_stripe_session(payment_data["payment_id"])

        order = order_repo.update(order)

        text = format_payment_link(payment_data["payment_url"], order.order_id)
        keyboard = get_stripe_payment_keyboard(
            payment_data["payment_url"], order.order_id
        )
        bot.send_message(
            order.chat_id,
            text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

        _notify_seller_new_order(bot, order, order_repo, seller_chat_id)

    except PaymentProviderError as e:
        logger.error(f"Stripe error: {e}")
        bot.send_message(
            order.chat_id,
            f"❌ Ошибка создания платежа: {e}\n" "Попробуйте выбрать оплату наличными.",
        )


def _handle_cash_payment(
    bot: telebot.TeleBot,
    order,
    order_repo: OrderRepository,
    seller_chat_id: str,
) -> None:
    """Processes the order with cash payment."""
    bot.send_message(
        order.chat_id,
        f"✅ <b>Заказ #{order.order_id} оформлен!</b>\n\n"
        f"{format_order_for_customer(order)}\n\n"
        f"Оплата наличными при получении. "
        f"Ожидайте подтверждения от менеджера.",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
    _notify_seller_new_order(bot, order, order_repo, seller_chat_id)


def _notify_seller_new_order(
    bot: telebot.TeleBot,
    order,
    order_repo: OrderRepository,
    seller_chat_id: str,
) -> None:
    """Notifies the seller of a new order."""
    if not seller_chat_id:
        return
    try:
        customer_name = get_customer_name(bot, order.chat_id)
        text = format_order_for_seller(order, customer_name)

        from presentation.keyboards.inline_keyboards import get_seller_order_keyboard

        msg = bot.send_message(
            seller_chat_id,
            text,
            parse_mode="HTML",
            reply_markup=get_seller_order_keyboard(order, stage="new"),
        )

        order.seller_message_id = msg.message_id
        order_repo.update(order)

    except Exception as e:
        logger.error(f"Seller notification error: {e}")


def _notify_seller_paid(
    bot: telebot.TeleBot,
    order,
    order_repo: OrderRepository,
    seller_chat_id: str,
) -> None:
    """Notifies the seller when the order has been paid."""
    if not seller_chat_id:
        return
    try:
        customer_name = get_customer_name(bot, order.chat_id)
        text = (
            f"💳 <b>ЗАКАЗ #{order.order_id} ОПЛАЧЕН!</b>\n\n"
            + format_order_for_seller(order, customer_name)
        )
        from presentation.keyboards.inline_keyboards import get_seller_order_keyboard

        msg = bot.send_message(
            seller_chat_id,
            text,
            parse_mode="HTML",
            reply_markup=get_seller_order_keyboard(order, stage="new"),
        )

        if not order.seller_message_id:
            order.seller_message_id = msg.message_id
            order_repo.update(order)

    except Exception as e:
        logger.error(f"Seller paid notification error: {e}")


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


_cleanup_thread = threading.Thread(
    target=_cleanup_expired_checkouts,
    name="CheckoutCleanup",
    daemon=True,
)
_cleanup_thread.start()
