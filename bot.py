import logging
import telebot
from telebot import types

from data_loader import CatalogLoader
import config

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Инициализация бота и загрузчика каталога
bot = telebot.TeleBot(config.BOT_TOKEN)
loader = CatalogLoader(path=config.EXCEL_PATH)


@bot.message_handler(commands=["start"])
def handle_start(message):
    text = (
        "Привет! Я бот-магазин.\n\n"
        "Доступные команды:\n"
        "/categories – посмотреть категории товаров\n"
        "/catalog – всё сразу"
    )
    bot.send_message(message.chat.id, text)


@bot.message_handler(commands=["categories"])
def handle_categories(message):
    cats = loader.get_categories()
    if not cats:
        bot.send_message(message.chat.id, "Категорий пока нет.")
        return

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )
    for cat in cats:
        markup.add(types.KeyboardButton(cat))

    bot.send_message(
        message.chat.id,
        "Выберите категорию:",
        reply_markup=markup
    )


@bot.message_handler(commands=["catalog"])
def handle_catalog(message):
    items = loader.data  # предполагаем loader.data — dict всех позиций
    if not items:
        bot.send_message(message.chat.id, "Каталог пуст.")
        return

    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        btn_text = f"{info['name']} — {info['price']}₽"
        markup.add(
            types.InlineKeyboardButton(
                text=btn_text,
                callback_data=f"buy_{item_id}"
            )
        )

    bot.send_message(
        message.chat.id,
        "Весь каталог товаров:",
        reply_markup=markup
    )


@bot.message_handler(func=lambda msg: msg.text in loader.get_categories())
def handle_category_selection(message):
    items = loader.get_by_category(message.text)
    if not items:
        bot.send_message(message.chat.id, "В этой категории пока пусто.")
        return

    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        btn_text = f"{info['name']} — {info['price']}₽"
        markup.add(
            types.InlineKeyboardButton(
                text=btn_text,
                callback_data=f"buy_{item_id}"
            )
        )

    bot.send_message(
        message.chat.id,
        "Товары в категории «" + message.text + "»:",
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("buy_"))
def handle_buy(call):
    try:
        item_id = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        bot.answer_callback_query(call.id, "Неверный идентификатор товара.")
        logging.warning("Некорректный callback_data: %s", call.data)
        return

    info = loader.data.get(item_id)
    if not info:
        bot.answer_callback_query(call.id, "Товар не найден.")
        return

    if info["stock"] <= 0:
        bot.answer_callback_query(call.id, "К сожалению, этот товар закончился.")
        return

    # уменьшаем остаток
    loader.reduce_stock(item_id, qty=1)
    bot.answer_callback_query(call.id, f"Вы купили {info['name']}! Спасибо за покупку.")


if __name__ == "__main__":
    logging.info("Запуск бота...")
    bot.infinity_polling(
        timeout=60,
        long_polling_timeout=5
    )
