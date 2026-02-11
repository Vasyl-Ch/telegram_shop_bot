"""
InlineKeyboard keyboard for messages."""

from telebot import types
from typing import List

from domain.entities.product import Product
from domain.entities.cart import Cart
from domain.entities.order import Order
from domain.enums.payment_method import PaymentMethod


def get_categories_keyboard(categories: List[str]) -> types.InlineKeyboardMarkup:
    """
    List of categories.

    Args:
        categories: List of category names

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    for category in categories:
        markup.add(
            types.InlineKeyboardButton(
                text=f"📂 {category}", callback_data=f"cat:{category}"
            )
        )
    return markup


def get_products_keyboard(
    products: List[Product], category: str
) -> types.InlineKeyboardMarkup:
    """
    List of products in the category.

    Args:
        products: List of products
        category: Category name (for the "Back" button)

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    for product in products:
        stock_label = (
            f"({product.stock} шт.)" if product.is_available else "(нет в наличии)"
        )
        markup.add(
            types.InlineKeyboardButton(
                text=f"{product.name} — {product.price}₴ {stock_label}",
                callback_data=f"prod:{product.product_id}",
            )
        )

    if category == "catalog":
        pass
    elif category == "search":
        markup.add(
            types.InlineKeyboardButton(
                text="⬅️ Назад к каталогу", callback_data="back:catalog"
            )
        )
    else:
        markup.add(
            types.InlineKeyboardButton(
                text="⬅️ Назад к категориям", callback_data="back:categories"
            )
        )

    return markup


def get_product_detail_keyboard(
    product: Product, from_category: str
) -> types.InlineKeyboardMarkup:
    """
    Detailed product card with an add to cart button.

    Args:
        product: Commodity
        from_category: Category (for Back button)

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    if product.is_available:
        markup.add(
            types.InlineKeyboardButton(
                text="➕ Добавить в корзину", callback_data=f"add:{product.product_id}"
            )
        )
    else:
        markup.add(
            types.InlineKeyboardButton(text="❌ Нет в наличии", callback_data="noop")
        )

    markup.add(
        types.InlineKeyboardButton(
            text=f"⬅️ Назад к категории", callback_data=f"cat:{from_category}"
        )
    )
    return markup


def get_cart_keyboard(cart: Cart) -> types.InlineKeyboardMarkup:
    """
    Recycle bin control keypad.

    Args:
        cart: Shopping cart

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=2)

    for item in cart.get_items_list():
        markup.row(
            types.InlineKeyboardButton(
                text=f"➖ {item.name}", callback_data=f"cart_dec:{item.product_id}"
            ),
            types.InlineKeyboardButton(
                text=f"➕ {item.name}", callback_data=f"cart_inc:{item.product_id}"
            ),
        )

    if not cart.is_empty():
        markup.add(
            types.InlineKeyboardButton(
                text="🚚 Оформить заказ", callback_data="checkout:start"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="🗑 Очистить корзину", callback_data="cart:clear"
        )
    )
    return markup


def get_payment_method_keyboard() -> types.InlineKeyboardMarkup:
    """
    Choosing a payment method.

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)

    for method in PaymentMethod:
        markup.add(
            types.InlineKeyboardButton(
                text=method.display_name, callback_data=f"pay_method:{method.value}"
            )
        )

    markup.add(
        types.InlineKeyboardButton(
            text="❌ Отменить заказ", callback_data="checkout:cancel"
        )
    )
    return markup


def get_stripe_payment_keyboard(
    payment_url: str, order_id: int
) -> types.InlineKeyboardMarkup:
    """
    Button to go to Stripe payment.

    Args:
        payment_url: URL Stripe Checkout Session
        order_id: Order ID

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton(text="💳 Оплатить картой", url=payment_url))
    markup.add(
        types.InlineKeyboardButton(
            text="🔄 Проверить оплату", callback_data=f"check_payment:{order_id}"
        )
    )
    markup.add(
        types.InlineKeyboardButton(
            text="❌ Отменить заказ", callback_data=f"cancel_order:{order_id}"
        )
    )
    return markup


def get_seller_order_keyboard(
    order: Order, stage: str = "new"
) -> types.InlineKeyboardMarkup:
    """
    Order management keypad for the seller.

    Args:
        order: Order
        stage: Order stage ("new", "confirmed")

    Returns:
        InlineKeyboardMarkup
    """
    markup = types.InlineKeyboardMarkup(row_width=2)
    oid = order.order_id

    if stage == "new":
        markup.row(
            types.InlineKeyboardButton(
                text="✅ Подтвердить", callback_data=f"seller_confirm:{oid}"
            ),
            types.InlineKeyboardButton(
                text="❌ Отменить", callback_data=f"seller_cancel:{oid}"
            ),
        )
    elif stage == "confirmed":
        markup.add(
            types.InlineKeyboardButton(
                text="🚚 Доставлен", callback_data=f"seller_deliver:{oid}"
            )
        )
        markup.add(
            types.InlineKeyboardButton(
                text="❌ Отменить", callback_data=f"seller_cancel:{oid}"
            )
        )

    return markup


def get_order_list_keyboard(orders: List[Order]) -> types.InlineKeyboardMarkup:
    """
    A list of the user's orders.

    Args:
        orders: List of orders

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
                    f"{order.total_amount}₴"
                ),
                callback_data=f"order_detail:{order.order_id}",
            )
        )

    return markup
