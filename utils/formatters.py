"""
Форматирование сообщений для Telegram.

Централизованные функции для единообразного отображения данных.
Принцип Single Responsibility: только форматирование.
"""

from decimal import Decimal
from datetime import datetime
from typing import List, Optional

from domain.entities.order import Order
from domain.entities.cart import Cart
from domain.entities.product import Product


def format_price(amount: Decimal) -> str:
    """
    Форматирует цену для отображения.

    Args:
        amount: Сумма

    Returns:
        str: Отформатированная цена (например "1 250.00₽")
    """
    return f"{amount:,.2f}₽".replace(",", " ")


def format_product_card(product: Product) -> str:
    """
    Формирует карточку товара.

    Args:
        product: Товар

    Returns:
        str: Текст карточки товара для Telegram
    """
    return (
        f"🏷 <b>{product.name}</b>\n"
        f"💰 Цена: <b>{format_price(product.price)}</b>\n"
        f"📦 {product.stock_status}\n"
        f"🗂 Категория: {product.category}"
    )


def format_cart(cart: Cart) -> str:
    """
    Формирует сообщение с содержимым корзины.

    Args:
        cart: Корзина покупателя

    Returns:
        str: Текст корзины для Telegram
    """
    if cart.is_empty():
        return "🛍 Ваша корзина пуста."

    lines = ["🛍 <b>Ваша корзина:</b>\n"]

    for item in cart.get_items_list():
        lines.append(
            f"• {item.name} "
            f"×{item.quantity} — "
            f"{format_price(item.total)}"
        )

    lines.append(f"\n💰 <b>Итого: {format_price(cart.get_total())}</b>")
    lines.append(f"📦 Товаров: {cart.get_items_count()} шт.")

    return "\n".join(lines)


def format_order_for_customer(order: Order) -> str:
    """
    Формирует сообщение о заказе для покупателя.

    Args:
        order: Заказ

    Returns:
        str: Текст заказа для отправки покупателю
    """
    lines = [
        f"📦 <b>Заказ #{order.order_id}</b>\n",
        f"📊 Статус: {order.status.display_name}",
    ]

    if order.payment_method:
        lines.append(f"💳 Оплата: {order.payment_method.display_name}")

    lines.append("\n<b>Товары:</b>")
    for item in order.items:
        lines.append(
            f"• {item.name} ×{item.quantity} — {format_price(item.total)}"
        )

    lines.extend([
        f"\n💰 <b>Итого: {format_price(order.total_amount)}</b>",
        f"📱 Телефон: {order.phone}",
        f"🏠 Адрес: {order.address}",
        f"📅 Создан: {order.created_at.strftime('%d.%m.%Y %H:%M')}",
    ])

    return "\n".join(lines)


def format_order_for_seller(order: Order, customer_name: str) -> str:
    """
    Формирует уведомление о заказе для продавца.

    Args:
        order: Заказ
        customer_name: Имя покупателя

    Returns:
        str: Текст уведомления для продавца
    """
    lines = [
        f"🔔 <b>НОВЫЙ ЗАКАЗ #{order.order_id}!</b>\n",
        f"👤 Клиент: {customer_name}",
        f"📱 Телефон: {order.phone}",
        f"🏠 Адрес: {order.address}\n",
        "<b>📦 Заказанные товары:</b>",
    ]

    for item in order.items:
        lines.append(
            f"• {item.name} ×{item.quantity} — {format_price(item.total)}"
        )

    payment_info = (
        order.payment_method.display_name
        if order.payment_method
        else "не выбран"
    )

    lines.extend([
        f"\n💳 Способ оплаты: {payment_info}",
        f"💰 <b>Общая сумма: {format_price(order.total_amount)}</b>",
        f"📊 Статус: {order.status.display_name}",
    ])

    return "\n".join(lines)


def format_payment_link(payment_url: str, order_id: int) -> str:
    """
    Формирует сообщение со ссылкой на оплату.

    Args:
        payment_url: URL страницы оплаты Stripe
        order_id: ID заказа

    Returns:
        str: Сообщение для пользователя
    """
    return (
        f"💳 <b>Оплата заказа #{order_id}</b>\n\n"
        f"Для оплаты картой нажмите кнопку ниже.\n"
        f"Ссылка действительна <b>4 часа</b>.\n\n"
        f"После успешной оплаты статус заказа обновится автоматически.\n\n"
        f"🔗 <a href='{payment_url}'>Перейти к оплате</a>"
    )


def format_order_status_update(order: Order) -> str:
    """
    Формирует сообщение об изменении статуса заказа.

    Args:
        order: Заказ с обновленным статусом

    Returns:
        str: Текст уведомления об изменении статуса
    """
    status_messages = {
        "paid": (
            f"✅ Ваш заказ #{order.order_id} оплачен!\n\n"
            "Ожидайте подтверждения от менеджера."
        ),
        "confirmed": (
            f"✅ Ваш заказ #{order.order_id} подтверждён!\n\n"
            "Менеджер подтвердил ваш заказ. Ожидайте доставки."
        ),
        "delivered": (
            f"🎉 Ваш заказ #{order.order_id} доставлен!\n\n"
            "Спасибо за покупку! Будем рады видеть вас снова. 🛒"
        ),
        "cancelled": (
            f"❌ Ваш заказ #{order.order_id} отменён.\n\n"
            "Свяжитесь с продавцом для уточнения деталей."
        ),
        "failed": (
            f"⚠️ Оплата заказа #{order.order_id} не прошла.\n\n"
            "Попробуйте оформить заказ заново."
        ),
    }

    return status_messages.get(
        order.status.value,
        f"🔄 Статус заказа #{order.order_id} обновлён: "
        f"{order.status.display_name}"
    )