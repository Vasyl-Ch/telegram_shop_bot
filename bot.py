import logging
import telebot
from telebot import types

from data_loader import CatalogLoader
import config

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

bot = telebot.TeleBot(config.BOT_TOKEN)
loader = CatalogLoader(path=config.EXCEL_PATH)

# Хранение корзин: {chat_id: {item_id: quantity}}
user_carts = {}


def get_cart(chat_id):
    return user_carts.setdefault(chat_id, {})


@bot.message_handler(commands=["start"])
def handle_start(message):
    text = (
        "Привет! Я бот-магазин.\n\n"
        "Доступные команды:\n"
        "/categories – посмотреть категории товаров\n"
        "/catalog – весь каталог\n"
        "/cart – просмотреть корзину"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["catalog"])
def handle_catalog(message):
    items = loader.data
    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        btn_text = f"{info['name']} — {info['price']}₽"
        markup.add(types.InlineKeyboardButton(
            text=btn_text,
            callback_data=f"add_{item_id}"
        ))
    bot.send_message(message.chat.id, "Весь каталог:", reply_markup=markup)


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
    cart[item_id] = cart.get(item_id, 0) + 1
    bot.answer_callback_query(call.id, f"Добавлено «{info['name']}» (в корзине: {cart[item_id]})")


@bot.message_handler(commands=["cart"])
def handle_view_cart(message):
    chat_id = message.chat.id
    cart = get_cart(chat_id)

    if not cart:
        return bot.send_message(chat_id, "Ваша корзина пуста.")

    text_lines = []
    total = 0
    markup = types.InlineKeyboardMarkup()
    for item_id, qty in cart.items():
        info = loader.data[item_id]
        cost = info["price"] * qty
        total += cost
        text_lines.append(f"{info['name']} ×{qty} — {cost}₽")
        # Кнопка для удаления по одному
        markup.add(types.InlineKeyboardButton(
            text=f"– {info['name']}",
            callback_data=f"remove_{item_id}"
        ))

    text = "\n".join(text_lines) + f"\n\nИтого: {total}₽"
    # Добавляем кнопку оформления
    markup.add(types.InlineKeyboardButton(text="Оформить заказ", callback_data="checkout"))
    bot.send_message(chat_id, text, reply_markup=markup)


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
    bot.answer_callback_query(call.id, "Товар удалён из корзины.")


@bot.callback_query_handler(func=lambda c: c.data == "checkout")
def handle_checkout(call):
    chat_id = call.message.chat.id
    cart = get_cart(chat_id)

    if not cart:
        return bot.answer_callback_query(call.id, "Корзина пуста.")

    # Проверка наличия и уменьшение стока
    summary = []
    for item_id, qty in list(cart.items()):
        info = loader.data[item_id]
        if info["stock"] < qty:
            summary.append(f"{info['name']} в количестве {qty} — нет в наличии")
            continue
        loader.reduce_stock(item_id, qty)
        summary.append(f"{info['name']} ×{qty} — оформлено")
        del cart[item_id]

    bot.answer_callback_query(call.id, "Заказ оформлен!")
    bot.send_message(chat_id, "Результаты:\n" + "\n".join(summary))


if __name__ == "__main__":
    logging.info("Запуск бота...")
    bot.infinity_polling(timeout=60, long_polling_timeout=5)
