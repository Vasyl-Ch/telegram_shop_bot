import logging
import telebot
from telebot import types
import threading
import time
import os
from dotenv import load_dotenv

from data_loader import CatalogLoader

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

# Загружаем переменные окружения из файла .env
load_dotenv()

# Получаем данные из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
EXCEL_PATH = os.getenv("EXCEL_PATH")
SELLER_CHAT_ID = os.getenv("SELLER_CHAT_ID")

# Создаем бота и загрузчик каталога
bot = telebot.TeleBot(BOT_TOKEN)
loader = CatalogLoader(EXCEL_PATH)

# Хранение корзин: {chat_id: {item_id: quantity}}
user_carts = {}
# Хранение информации о заказах: {chat_id: {'cart': {}, 'phone': '', 'address': ''}}
user_orders = {}


def get_cart(chat_id):
    return user_carts.setdefault(chat_id, {})


def auto_reload_catalog():
    """Автоматически перезагружает каталог каждые 5 минут"""
    while True:
        time.sleep(300)  # 5 минут
        try:
            loader.reload()
            logging.info("Каталог автоматически обновлен")
        except Exception as e:
            logging.error(f"Ошибка при обновлении каталога: {e}")


# Запускаем фоновое обновление каталога
reload_thread = threading.Thread(target=auto_reload_catalog, daemon=True)
reload_thread.start()


@bot.message_handler(commands=["start"])
def handle_start(message):
    text = (
        "🛒 Добро пожаловать в наш интернет-магазин!\n\n"
        "Доступные команды:\n"
        "🗂 /categories – посмотреть категории товаров\n"
        "📋 /catalog – весь каталог\n"
        "🛍 /cart – просмотреть корзину\n"
        "🔄 /reload – обновить каталог (для администрации)"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["categories"])
def handle_categories(message):
    categories = loader.get_categories()
    if not categories:
        return bot.send_message(message.chat.id, "Категории товаров не найдены.")

    markup = types.InlineKeyboardMarkup()
    for category in categories:
        markup.add(types.InlineKeyboardButton(
            text=f"📂 {category}",
            callback_data=f"category_{category}"
        ))

    bot.send_message(message.chat.id, "🗂 Выберите категорию:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("category_"))
def handle_category_selection(call):
    category = call.data.split("_", 1)[1]
    items = loader.get_by_category(category)

    if not items:
        return bot.answer_callback_query(call.id, "В этой категории нет товаров.")

    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        stock_info = f" (осталось: {info['stock']})" if info['stock'] > 0 else " (нет в наличии)"
        btn_text = f"{info['name']} — {info['price']}₽{stock_info}"
        markup.add(types.InlineKeyboardButton(
            text=btn_text,
            callback_data=f"item_{item_id}"
        ))

    # Кнопка возврата к категориям
    markup.add(types.InlineKeyboardButton(
        text="⬅️ Назад к категориям",
        callback_data="back_to_categories"
    ))

    bot.edit_message_text(
        text=f"📂 Категория: {category}",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "back_to_categories")
def handle_back_to_categories(call):
    categories = loader.get_categories()
    markup = types.InlineKeyboardMarkup()
    for category in categories:
        markup.add(types.InlineKeyboardButton(
            text=f"📂 {category}",
            callback_data=f"category_{category}"
        ))

    bot.edit_message_text(
        text="🗂 Выберите категорию:",
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("item_"))
def handle_item_details(call):
    item_id = int(call.data.split("_")[1])
    info = loader.data.get(item_id)

    if not info:
        return bot.answer_callback_query(call.id, "Товар не найден.")

    # Формируем детальную информацию о товаре
    text = (
        f"🏷 {info['name']}\n"
        f"💰 Цена: {info['price']}₽\n"
        f"📦 В наличии: {info['stock']} шт.\n"
        f"🗂 Категория: {info['category']}"
    )

    markup = types.InlineKeyboardMarkup()
    if info['stock'] > 0:
        markup.add(types.InlineKeyboardButton(
            text="➕ Добавить в корзину",
            callback_data=f"add_{item_id}"
        ))
    else:
        markup.add(types.InlineKeyboardButton(
            text="❌ Нет в наличии",
            callback_data="unavailable"
        ))

    markup.add(types.InlineKeyboardButton(
        text="⬅️ Назад к категории",
        callback_data=f"category_{info['category']}"
    ))

    # Если есть изображение, отправляем фото с описанием
    if info.get('image_url') and info['image_url'].strip():
        try:
            bot.send_photo(
                call.message.chat.id,
                info['image_url'],
                caption=text,
                reply_markup=markup
            )
        except Exception as e:
            logging.error(f"Ошибка загрузки изображения: {e}")
            bot.send_message(call.message.chat.id, text, reply_markup=markup)
    else:
        bot.send_message(call.message.chat.id, text, reply_markup=markup)


@bot.message_handler(commands=["catalog"])
def handle_catalog(message):
    items = loader.data
    if not items:
        return bot.send_message(message.chat.id, "Каталог пуст.")

    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        stock_info = f" (осталось: {info['stock']})" if info['stock'] > 0 else " (нет в наличии)"
        btn_text = f"{info['name']} — {info['price']}₽{stock_info}"
        markup.add(types.InlineKeyboardButton(
            text=btn_text,
            callback_data=f"item_{item_id}"
        ))
    bot.send_message(message.chat.id, "📋 Весь каталог:", reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("add_"))
def handle_add_to_cart(call):
    chat_id = call.message.chat.id
    item_id = int(call.data.split("_")[1])
    info = loader.data.get(item_id)

    if not info:
        return bot.answer_callback_query(call.id, "Товар не найден.")
    if info["stock"] <= 0:
        return bot.answer_callback_query(call.id, "Товар закончился.")

    cart = get_cart(chat_id)
    current_in_cart = cart.get(item_id, 0)

    # Проверяем, не превышает ли количество в корзине доступный остаток
    if current_in_cart >= info["stock"]:
        return bot.answer_callback_query(call.id, "Нельзя добавить больше доступного количества.")

    cart[item_id] = current_in_cart + 1
    bot.answer_callback_query(call.id, f"✅ Добавлено «{info['name']}» (в корзине: {cart[item_id]})")


@bot.message_handler(commands=["cart"])
def handle_view_cart(message):
    chat_id = message.chat.id
    cart = get_cart(chat_id)

    if not cart:
        return bot.send_message(chat_id, "🛍 Ваша корзина пуста.")

    text_lines = ["🛍 Ваша корзина:\n"]
    total = 0
    markup = types.InlineKeyboardMarkup()

    for item_id, qty in cart.items():
        info = loader.data.get(item_id)
        if not info:  # Товар мог быть удален из каталога
            continue

        cost = info["price"] * qty
        total += cost
        text_lines.append(f"• {info['name']} ×{qty} — {cost}₽")

        # Кнопки для изменения количества
        markup.row(
            types.InlineKeyboardButton(
                text=f"➖ {info['name']}",
                callback_data=f"remove_{item_id}"
            ),
            types.InlineKeyboardButton(
                text=f"➕ {info['name']}",
                callback_data=f"add_cart_{item_id}"
            )
        )

    text_lines.append(f"\n💰 Итого: {total}₽")
    text = "\n".join(text_lines)

    if total > 0:
        markup.add(types.InlineKeyboardButton(
            text="🚚 Оформить заказ",
            callback_data="checkout"
        ))

    markup.add(types.InlineKeyboardButton(
        text="🗑 Очистить корзину",
        callback_data="clear_cart"
    ))

    bot.send_message(chat_id, text, reply_markup=markup)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("add_cart_"))
def handle_add_from_cart(call):
    chat_id = call.message.chat.id
    item_id = int(call.data.split("_")[2])
    info = loader.data.get(item_id)

    if not info:
        return bot.answer_callback_query(call.id, "Товар не найден.")

    cart = get_cart(chat_id)
    current_in_cart = cart.get(item_id, 0)

    if current_in_cart >= info["stock"]:
        return bot.answer_callback_query(call.id, "Нельзя добавить больше доступного количества.")

    cart[item_id] = current_in_cart + 1
    bot.answer_callback_query(call.id, f"➕ Добавлено")

    # Обновляем сообщение с корзиной
    handle_view_cart_update(call.message)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("remove_"))
def handle_remove_from_cart(call):
    chat_id = call.message.chat.id
    item_id = int(call.data.split("_")[1])
    cart = get_cart(chat_id)

    if item_id not in cart:
        return bot.answer_callback_query(call.id, "Нет такого товара в корзине.")

    cart[item_id] -= 1
    if cart[item_id] <= 0:
        del cart[item_id]

    bot.answer_callback_query(call.id, "➖ Товар удален")

    # Обновляем сообщение с корзиной
    handle_view_cart_update(call.message)


def handle_view_cart_update(message):
    """Обновляет сообщение с корзиной"""
    chat_id = message.chat.id
    cart = get_cart(chat_id)

    if not cart:
        text = "🛍 Ваша корзина пуста."
        markup = types.InlineKeyboardMarkup()
    else:
        text_lines = ["🛍 Ваша корзина:\n"]
        total = 0
        markup = types.InlineKeyboardMarkup()

        for item_id, qty in cart.items():
            info = loader.data.get(item_id)
            if not info:
                continue

            cost = info["price"] * qty
            total += cost
            text_lines.append(f"• {info['name']} ×{qty} — {cost}₽")

            markup.row(
                types.InlineKeyboardButton(
                    text=f"➖ {info['name']}",
                    callback_data=f"remove_{item_id}"
                ),
                types.InlineKeyboardButton(
                    text=f"➕ {info['name']}",
                    callback_data=f"add_cart_{item_id}"
                )
            )

        text_lines.append(f"\n💰 Итого: {total}₽")
        text = "\n".join(text_lines)

        if total > 0:
            markup.add(types.InlineKeyboardButton(
                text="🚚 Оформить заказ",
                callback_data="checkout"
            ))

        markup.add(types.InlineKeyboardButton(
            text="🗑 Очистить корзину",
            callback_data="clear_cart"
        ))

    try:
        bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message.message_id,
            reply_markup=markup
        )
    except:
        pass  # Сообщение уже обновлено или удалено


@bot.callback_query_handler(func=lambda c: c.data == "clear_cart")
def handle_clear_cart(call):
    chat_id = call.message.chat.id
    user_carts[chat_id] = {}
    bot.answer_callback_query(call.id, "🗑 Корзина очищена")

    text = "🛍 Ваша корзина пуста."
    markup = types.InlineKeyboardMarkup()

    bot.edit_message_text(
        text=text,
        chat_id=chat_id,
        message_id=call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda c: c.data == "checkout")
def handle_checkout(call):
    chat_id = call.message.chat.id
    cart = get_cart(chat_id)

    if not cart:
        return bot.answer_callback_query(call.id, "Корзина пуста.")

    # Сохраняем корзину для оформления заказа
    user_orders[chat_id] = {'cart': cart.copy(), 'phone': '', 'address': ''}

    bot.answer_callback_query(call.id, "Оформляем заказ...")
    bot.send_message(
        chat_id,
        "📱 Для оформления заказа укажите ваш номер телефона:\n"
        "(например: +373 69 123456)"
    )
    bot.register_next_step_handler_by_chat_id(chat_id, get_phone_number)


def get_phone_number(message):
    chat_id = message.chat.id
    phone = message.text.strip()

    if len(phone) < 10:
        bot.send_message(chat_id, "❌ Некорректный номер телефона. Попробуйте еще раз:")
        bot.register_next_step_handler_by_chat_id(chat_id, get_phone_number)
        return

    user_orders[chat_id]['phone'] = phone
    bot.send_message(
        chat_id,
        "🏠 Теперь укажите адрес доставки:"
    )
    bot.register_next_step_handler_by_chat_id(chat_id, get_delivery_address)


def get_delivery_address(message):
    chat_id = message.chat.id
    address = message.text.strip()

    if len(address) < 10:
        bot.send_message(chat_id, "❌ Адрес слишком короткий. Укажите полный адрес:")
        bot.register_next_step_handler_by_chat_id(chat_id, get_delivery_address)
        return

    user_orders[chat_id]['address'] = address
    finalize_order(chat_id)


def finalize_order(chat_id):
    order = user_orders.get(chat_id)
    if not order:
        return

    cart = order['cart']
    phone = order['phone']
    address = order['address']

    # Проверка наличия и финализация заказа
    summary = []
    total_cost = 0
    successful_items = []

    for item_id, qty in list(cart.items()):
        info = loader.data.get(item_id)
        if not info:
            summary.append(f"❌ {item_id} — товар не найден")
            continue

        if info["stock"] < qty:
            summary.append(f"❌ {info['name']} (заказано: {qty}, доступно: {info['stock']})")
            continue

        # Успешный товар
        cost = info['price'] * qty
        total_cost += cost
        loader.reduce_stock(item_id, qty)
        summary.append(f"✅ {info['name']} ×{qty} — {cost}₽")
        successful_items.append({
            'name': info['name'],
            'quantity': qty,
            'price': info['price'],
            'cost': cost
        })

    # Очищаем корзину пользователя
    user_carts[chat_id] = {}
    del user_orders[chat_id]

    # Отправляем подтверждение пользователю
    user_message = (
            f"🎉 Заказ оформлен!\n\n"
            f"📱 Телефон: {phone}\n"
            f"🏠 Адрес: {address}\n\n"
            f"📦 Товары:\n" + "\n".join(summary) +
            f"\n\n💰 Итого: {total_cost}₽\n\n"
            f"🚚 Ожидайте звонка для уточнения деталей доставки."
    )
    bot.send_message(chat_id, user_message)

    # Отправляем уведомление продавцу
    if successful_items and SELLER_CHAT_ID:
        user_info = bot.get_chat(chat_id)
        customer_name = f"{user_info.first_name} {user_info.last_name or ''}".strip()
        if not customer_name:
            customer_name = user_info.username or f"ID: {chat_id}"

        seller_message = (
            f"🔔 НОВЫЙ ЗАКАЗ!\n\n"
            f"👤 Клиент: {customer_name}\n"
            f"📱 Телефон: {phone}\n"
            f"🏠 Адрес: {address}\n\n"
            f"📦 Заказанные товары:\n"
        )

        for item in successful_items:
            seller_message += f"• {item['name']} ×{item['quantity']} — {item['cost']}₽\n"

        seller_message += f"\n💰 Общая сумма: {total_cost}₽"

        try:
            bot.send_message(SELLER_CHAT_ID, seller_message)
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления продавцу: {e}")


@bot.message_handler(commands=["reload"])
def handle_reload_catalog(message):
    try:
        loader.reload()
        bot.send_message(message.chat.id, "✅ Каталог обновлен!")
        logging.info(f"Каталог обновлен пользователем {message.chat.id}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка обновления каталога: {str(e)}")
        logging.error(f"Ошибка обновления каталога: {e}")


@bot.callback_query_handler(func=lambda c: c.data == "unavailable")
def handle_unavailable(call):
    bot.answer_callback_query(call.id, "Товар временно отсутствует")


if __name__ == "__main__":
    logging.info("🚀 Запуск бота...")
    bot.infinity_polling(timeout=60, long_polling_timeout=5)