import telebot
from telebot import types
from data_loader import CatalogLoader

TOKEN = "'8240324816:AAFrPPKzopVrRr769LKtnQpipvziiu8N0bU'"
bot = telebot.TeleBot(TOKEN)
loader = CatalogLoader(path="catalog.xlsx")

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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    for cat in cats:
        markup.add(types.KeyboardButton(cat))
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text in loader.get_categories())
def handle_category_selection(message):
    items = loader.get_by_category(message.text)
    if not items:
        bot.send_message(message.chat.id, "В этой категории пусто.")
        return

    markup = types.InlineKeyboardMarkup()
    for item_id, info in items.items():
        btn_text = f"{info['name']} — {info['price']}₽"
        markup.add(types.InlineKeyboardButton(text=btn_text, callback_data=f"buy_{item_id}"))

    bot.send_message(message.chat.id, "Товары:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("buy_"))
def handle_buy(call):
    item_id = int(call.data.split("_")[1])
    info = loader.data.get(item_id)
    if not info:
        bot.answer_callback_query(call.id, "Товар не найден.")
        return

    if info["stock"] <= 0:
        bot.answer_callback_query(call.id, "К сожалению, товар закончился.")
        return

    # уменьшаем остаток
    loader.reduce_stock(item_id, qty=1)
    bot.answer_callback_query(call.id, f"Вы купили {info['name']}!")

if __name__ == "__main__":
    bot.infinity_polling()
q


