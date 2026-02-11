"""
InlineKeyboard клавиатуры для сообщений.
"""

from telebot import types
from typing import List

from domain.entities.product import Product
from domain.entities.cart import Cart
from domain.entities.order import Order
from domain.enums.payment_method import PaymentMethod


def get_categories_keyboard(categories: List[str]) -> types.InlineKeyboardMarkup:
    """
    Список категорий.

    Args:
        categories: Список названий категорий

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    for category in categories:
        markup.add(
            types.InlineKeyboardButton(
                text=f"📂 {category}",
                callback_data=f"cat:{category}"
            )
        )
    return markup


def get_products_keyboard(
    products: List[Product],
    category: str
) -> types.InlineKeyboardMarkup:
    """
    Список товаров в категории.

    Args:
        products: Список товаров
        category: Название категории (для кнопки "Назад")

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    for product in products:
        stock_label = (
            f"({product.stock} шт.)"
            if product.is_available
            else "(нет в наличии)"
        )
        markup.add(
            types.InlineKeyboardButton(
                text=f"{product.name} — {product.price}₽ {stock_label}",
                callback_data=f"prod:{product.product_id}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="⬅️ Назад к категориям",
            callback_data="back:categories"
        )
    )
    return markup


def get_product_detail_keyboard(
    product: Product,
    from_category: str
) -> types.InlineKeyboardMarkup:
    """
    Детальная карточка товара с кнопкой добавления в корзину.

    Args:
        product: Товар
        from_category: Категория (для кнопки "Назад")

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    if product.is_available:
        markup.add(
            types.InlineKeyboardButton(
                text="➕ Добавить в корзину",
                callback_data=f"add:{product.product_id}"
            )
        )
    else:
        markup.add(
            types.InlineKeyboardButton(
                text="❌ Нет в наличии",
                callback_data="noop"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text=f"⬅️ Назад к категории",
            callback_data=f"cat:{from_category}"
        )
    )
    return markup


def get_cart_keyboard(cart: Cart) -> types.InlineKeyboardMarkup:
    """
    Клавиатура управления корзиной.

    Args:
        cart: Корзина покупателя

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    for item in cart.get_items_list():
        markup.row(
            types.InlineKeyboardButton(
                text=f"➖ {item.name}",
                callback_data=f"cart_dec:{item.product_id}"
            ),
            types.InlineKeyboardButton(
                text=f"➕ {item.name}",
                callback_data=f"cart_inc:{item.product_id}"
            ),
        )

    if not cart.is_empty():
        markup.add(
            types.InlineKeyboardButton(
                text="🚚 Оформить заказ",
                callback_data="checkout:start"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="🗑 Очистить корзину",
            callback_data="cart:clear"
        )
    )
    return markup


def get_payment_method_keyboard() -> types.InlineKeyboardMarkup:
    """
    Выбор способа оплаты.

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    for method in PaymentMethod:
        markup.add(
            types.InlineKeyboardButton(
                text=method.display_name,
                callback_data=f"pay_method:{method.value}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data="checkout:cancel"
        )
    )
    return markup


def get_stripe_payment_keyboard(
    payment_url: str,
    order_id: int
) -> types.InlineKeyboardMarkup:
    """
    Кнопка для перехода к Stripe оплате.

    Args:
        payment_url: URL Stripe Checkout Session
        order_id: ID заказа

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(
            text="💳 Оплатить картой",
            url=payment_url
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            text="🔄 Проверить оплату",
            callback_data=f"check_payment:{order_id}"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data=f"cancel_order:{order_id}"
        )
    )
    return markup


def get_seller_order_keyboard(
    order: Order,
    stage: str = "new"
) -> types.InlineKeyboardMarkup:
    """
    Клавиатура управления заказом для продавца.

    Args:
        order: Заказ
        stage: Стадия заказа ("new", "confirmed")

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    oid = order.order_id

    if stage == "new":
        markup.row(
            types.InlineKeyboardButton(
                text="✅ Подтвердить",
                callback_data=f"seller_confirm:{oid}"
            ),
            types.InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"seller_cancel:{oid}"
            ),
        )
    elif stage == "confirmed":
        markup.add(
            types.InlineKeyboardButton(
                text="🚚 Доставлен",
                callback_data=f"seller_deliver:{oid}"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                text="❌ Отменить",
                callback_data=f"seller_cancel:{oid}"
            )
        )

    return markup


def get_order_list_keyboard(
    orders: List[Order]
) -> types.InlineKeyboardMarkup:
    """
    Список заказов пользователя.

    Args:
        orders: Список заказов

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    for order in orders[-5:]:  # Последние 5
        markup.add(
            types.InlineKeyboardButton(
                text=(
                    f"#{order.order_id} | "
                    f"{order.status.display_name} | "
                    f"{order.total_amount}₽"
                ),
                callback_data=f"order_detail:{order.order_id}"
            )
        )

    return markup