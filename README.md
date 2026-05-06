# 🛒 Telegram Shop Bot — Your Personal Seller 24/7! 
Hi there! 👋 I’ve built a powerful Telegram bot for online stores that works around the clock and turns your Telegram into a full-fledged shopping mall!

## 🚀 Why is it awesome? 
### 🌟 Superpowers of the bot: 
🎯 Smart product catalog — all items are stored in Google Sheets!
No more fiddling with Excel files — update your inventory right from the browser!

🛒 **Interactive cart** — add items with one click, change quantities, clear the cart — all without reloading!

📱 **Sleek interface** — beautiful buttons, emojis, smooth transitions between sections. Shopping becomes pure joy!

👨‍💼 **Seller dashboard** — get notified of new orders, confirm deliveries, manage order statuses right inside Telegram!

📊 **Auto-update** — the bot monitors catalog changes and refreshes data every 5 minutes!

🔍 **Product search** — instantly find items by name!

# 💡 How does it work? 
**You add products to a Google Sheet (just like Excel, but in the cloud!)**
**Customers enter the bot and browse products via a user-friendly menu** 
**The bot automatically processes orders and sends you notifications** 
**You confirm the order and update stock with a single click!**

# 🛠 Tech under the hood Python 3.8+
— **fast and reliable Google Sheets API** 
— **all data in the cloud Telegram Bot API**
— **maximum integration Multithreading**
— **runs without lag!**

# 📈 Who is this bot for? 
✅ **Small businesses** — launch your store in 5 minutes! 
✅ **Info-business** — sell digital products 
✅ **Artisans** — showcase handmade goods 
✅ **Dropshippers** — manage inventory with ease

# 🎯 Features you’ll love: 
✨ **No hosting required** — runs on any computer 
✨ **Works 24/7** — takes orders even while you sleep 
✨ **Automatic backups** — Google saves your data for you 
✨ **Multi-account** — multiple sellers can operate simultaneously

# 💰 How much does it cost?
**The best part — it's free!** 🎁

You only pay for a server (if you want), but you can run it on your own PC!

---

## 🔐 Setup and Obtaining Credentials

### 1. Telegram Bot Token
- Open [@BotFather](https://t.me/BotFather) in Telegram
- Send the `/newbot` command and follow the instructions
- Copy the received token to the `BOT_TOKEN` variable
- Copy the bot username to the `BOT_USERNAME` variable

### 2. Chat ID (SELLER_CHAT_ID and SUPPORT_MANAGER_ID)
- Open [@userinfobot](https://t.me/userinfobot) in Telegram
- The bot will automatically send you your Chat ID
- Copy the ID to the `SELLER_CHAT_ID` and `SUPPORT_MANAGER_ID` variables

### 3. Google Sheets API
**Step 1: Creating a project in Google Cloud Console**
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create a new project or select an existing one
- In the menu, go to "APIs & Services" → "Library"
- Find and enable "Google Sheets API" and "Google Drive API"

**Step 2: Creating a Service Account**
- Go to "APIs & Services" → "Credentials"
- Click "Create Credentials" → "Service Account"
- Fill in the name and description, click "Create and Continue"
- Skip granting roles (optional)
- Click "Done"

**Step 3: Getting the JSON key**
- In the Service Accounts list, find the created account
- Click on the account email
- Go to the "Keys" tab
- Click "Add Key" → "Create new key"
- Select "JSON" type and click "Create"
- The file will automatically download — save it as `credentials.json` in the project root

**Step 4: Setting up Google Sheets**
- Create a new Google spreadsheet or open an existing one
- Copy the spreadsheet ID from the URL (between `/d/` and `/edit`):
  ```
  https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit
  ```
- Open `credentials.json` and copy the Service Account email (the `client_email` field)
- In Google Sheets, click "Share" and grant "Editor" access to this email
- Paste the spreadsheet ID into the `GOOGLE_DISK_ID` variable

### 4. Stripe Payment Keys
- Sign up at [Stripe](https://stripe.com/)
- Go to the [Dashboard](https://dashboard.stripe.com/)
- In the "Developers" → "API keys" section, find:
  - **Publishable key** → copy to `STRIPE_PUBLISHABLE_KEY`
  - **Secret key** → copy to `STRIPE_SECRET_KEY`
- For testing, use test keys (starting with `pk_test_` and `sk_test_`)

### 5. Setting up Google Sheets Table

Your Google spreadsheet should contain the following columns (order matters):

| Column | Type | Required | Description | Example |
|--------|------|----------|-------------|---------|
| **id** | number | ✅ Yes | Unique product identifier | 1, 2, 3 |
| **brand** | text | ❌ No | Product brand/manufacturer | Nike, Apple |
| **name** | text | ✅ Yes | Product name | iPhone 15, Milk |
| **category** | text | ✅ Yes | Product category | Electronics, Food |
| **size_or_weight** | number | ❌ No | Product unit size/weight* | 2.5, 250, 0.5 |
| **price** | number | ✅ Yes | Product price** | 100, 250.50 |
| **unit_of_measurement** | text | ✅ Yes | Unit of measurement: "кг" (kg) or "шт" (pcs) | кг, шт |
| **stock** | number | ✅ Yes | Quantity in stock | 10, 0, 100 |
| **image_url** | text | ❌ No | Image URL (Google Drive supported) | https://drive.google.com/... |

**Important rules:**

**\* `size_or_weight` column:**
- For "кг" (kg) products: package weight in kilograms (e.g., 2.5 for a 2.5kg package)
- For "шт" (pcs) products:
  - If < 30: volume in liters (e.g., 0.5 for a 0.5L bottle)
  - If ≥ 30: weight in grams (e.g., 250 for a 250g package)

**\*\* `price` column:**
- For "кг" (kg) products: price per 1 kilogram
- For "шт" (pcs) products: price per 1 piece/package

**Filling examples:**

```
id | brand  | name           | category  | size_or_weight | price | unit_of_measurement | stock
1  | Farm   | Milk 2.5%      | Food      | 1.0           | 35    | л                   | 50
2  | Nike   | Sneakers       | Shoes     |               | 2500  | шт                  | 10
3  |        | Gouda Cheese   | Food      | 0.3           | 450   | кг                  | 5
4  | Lay's  | Chips          | Snacks    | 150           | 45    | шт                  | 30
```

**Images from Google Drive:**
- Upload the image to Google Drive
- Open the image and click "Share" → "Get link" → "Anyone with the link"
- Copy the link to the `image_url` column
- The bot will automatically convert the link to the correct format

### 6. Environment Variables Setup
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Fill in all values in the `.env` file with the obtained credentials
3. **IMPORTANT**: The `.env` and `credentials.json` files are in `.gitignore` and should not be committed to the repository!

---

## 🚀 Installation and Running

### Requirements
- Python 3.8 or higher
- pip (Python package manager)
- Git (for cloning the repository)

### Local Run

**1. Clone the repository:**
```bash
git clone https://github.com/Vasyl-Ch/telegram_shop_bot.git
cd telegram_shop_bot
```

**2. Create a virtual environment (recommended):**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python3 -m venv venv
source venv/bin/activate
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables:**
- Copy `.env.example` to `.env`
- Fill in all required variables (see "Setup and Obtaining Credentials" section)
- Place the `credentials.json` file in the project root

**5. Run the bot:**
```bash
python main.py
```

You should see the message:
```
✅ Bot started successfully
✅ GoogleSheetsClient initialized
```

### Running with Docker

**1. Make sure you have Docker and docker-compose installed:**
```bash
docker --version
docker-compose --version
```

**2. Configure environment variables:**
- Create `.env` file (see above)
- Make sure `credentials.json` is in the project root
- In `.env` change `JSON_KEY_FILE` to `/app/credentials.json`

**3. Build and run the container:**
```bash
docker-compose up -d
```

**4. Check logs:**
```bash
docker-compose logs -f telegram-bot
```

**5. Stop the bot:**
```bash
docker-compose down
```

**Useful Docker commands:**
```bash
# Rebuild container after changes
docker-compose build --no-cache

# Restart container
docker-compose restart

# View status
docker-compose ps

# Remove container and data
docker-compose down -v
```

---

**Want a bot like this for your business? 🚀**

📩 Message me on [Telegram](https://t.me/Vasilba1025) — I'll help you set it up and launch!

⭐ Star the repository if you like the project!

## License
This project is licensed under the CC BY-NC 4.0 License — see the [LICENSE](LICENSE) file for details.

---

*P.S. This bot is already generating real profits for stores! Don't miss your chance to automate your sales!* 💸

# 🛒 Telegram Магазин Бот — Твой личный продавец 24/7!

Привет! 👋 Я создал мощного Telegram бота для интернет-магазина, который работает круглосуточно и превращает твой телеграм в полноценный торговый центр! 

## 🚀 Почему это круто?

### 🌟 Супер-возможности бота:

🎯 **Умный каталог товаров** — все товары хранятся в Google Таблицах! Больше не нужно возиться с Excel файлами — обновляй ассортимент прямо из браузера!

🛒 **Интерактивная корзина** — добавляй товары одним кликом, меняй количество, очищай — всё без перезагрузки!

📱 **Стильный интерфейс** — красивые кнопки, emoji, плавные переходы между разделами. Покупать — одно удовольствие!

👨‍💼 **Панель продавца** — получай уведомления о новых заказах, подтверждай доставку, управляй статусами заказов прямо в телеграме!

📊 **Автообновление** — бот сам следит за изменениями в каталоге и подгружает актуальные данные каждые 5 минут!

🔍 **Поиск товаров** — находи нужные товары по названию моментально!

## 💡 Как это работает?

1. **Ты добавляешь товары** в Google Таблицу (как в обычном Excel, но в облаке!)
2. **Клиенты заходят в бота** и выбирают товары через удобное меню
3. **Бот автоматически** оформляет заказы и присылает тебе уведомления
4. **Ты подтверждаешь заказ** и списываешь остатки одним кликом!

## 🛠 Технологии под капотом

- **Python 3.8+** — быстрый и надежный
- **Google Sheets API** — все данные в облаке
- **Telegram Bot API** — максимальная интеграция
- **Многопоточность** — работает без тормозов!

## 📈 Для кого этот бот?

✅ **Малый бизнес** — запусти магазин за 5 минут!  
✅ **Инфобизнес** — продавай цифровые товары  
✅ **Ремесленники** — демонстрируй handmade товары  
✅ **Дропшипперы** — управляй ассортиментом легко  

## 🎯 Фишки, которые ты полюбишь:

✨ **Не требует хостинга** — запускается на любом компьютере  
✨ **Работает 24/7** — принимает заказы даже когда ты спишь  
✨ **Автоматическое резервное копирование** — Google сам сохраняет данные  
✨ **Мультиаккаунт** — несколько продавцов могут работать одновременно  

## 💰 Сколько стоит?

Самое приятное — **бесплатно!** 🎁
Ты платишь только за сервер (если хочешь), но можешь запустить и на своем ПК!

---

## 🔐 Настройка и получение учетных данных

### 1. Telegram Bot Token
- Откройте [@BotFather](https://t.me/BotFather) в Telegram
- Отправьте команду `/newbot` и следуйте инструкциям
- Скопируйте полученный токен в переменную `BOT_TOKEN`
- Скопируйте username бота в переменную `BOT_USERNAME`

### 2. Chat ID (SELLER_CHAT_ID и SUPPORT_MANAGER_ID)
- Откройте [@userinfobot](https://t.me/userinfobot) в Telegram
- Бот автоматически отправит ваш Chat ID
- Скопируйте ID в переменные `SELLER_CHAT_ID` и `SUPPORT_MANAGER_ID`

### 3. Google Sheets API
**Шаг 1: Создание проекта в Google Cloud Console**
- Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
- Создайте новый проект или выберите существующий
- В меню перейдите в "APIs & Services" → "Library"
- Найдите и включите "Google Sheets API" и "Google Drive API"

**Шаг 2: Создание Service Account**
- Перейдите в "APIs & Services" → "Credentials"
- Нажмите "Create Credentials" → "Service Account"
- Заполните имя и описание, нажмите "Create and Continue"
- Пропустите предоставление ролей (опционально)
- Нажмите "Done"

**Шаг 3: Получение JSON ключа**
- В списке Service Accounts найдите созданный аккаунт
- Нажмите на email аккаунта
- Перейдите на вкладку "Keys"
- Нажмите "Add Key" → "Create new key"
- Выберите тип "JSON" и нажмите "Create"
- Файл автоматически скачается — сохраните его как `credentials.json` в корень проекта

**Шаг 4: Настройка Google Sheets**
- Создайте новую Google таблицу или откройте существующую
- Скопируйте ID таблицы из URL (между `/d/` и `/edit`):
  ```
  https://docs.google.com/spreadsheets/d/ВАШ_ID_ТАБЛИЦЫ/edit
  ```
- Откройте `credentials.json` и скопируйте email Service Account (поле `client_email`)
- В Google таблице нажмите "Share" и предоставьте доступ "Editor" этому email
- Вставьте ID таблицы в переменную `GOOGLE_DISK_ID`

### 4. Stripe Payment Keys
- Зарегистрируйтесь на [Stripe](https://stripe.com/)
- Перейдите в [Dashboard](https://dashboard.stripe.com/)
- В разделе "Developers" → "API keys" найдите:
  - **Publishable key** → скопируйте в `STRIPE_PUBLISHABLE_KEY`
  - **Secret key** → скопируйте в `STRIPE_SECRET_KEY`
- Для тестирования используйте тестовые ключи (начинаются с `pk_test_` и `sk_test_`)

### 5. Настройка Google Sheets таблицы

Ваша Google таблица должна содержать следующие колонки (порядок важен):

| Колонка | Тип | Обязательная | Описание | Пример |
|---------|-----|--------------|----------|--------|
| **id** | число | ✅ Да | Уникальный идентификатор товара | 1, 2, 3 |
| **brand** | текст | ❌ Нет | Бренд/производитель товара | Nike, Apple |
| **name** | текст | ✅ Да | Название товара | iPhone 15, Молоко |
| **category** | текст | ✅ Да | Категория товара | Электроника, Продукты |
| **size_or_weight** | число | ❌ Нет | Размер/вес единицы товара* | 2.5, 250, 0.5 |
| **price** | число | ✅ Да | Цена товара** | 100, 250.50 |
| **unit_of_measurement** | текст | ✅ Да | Единица измерения: "кг" или "шт" | кг, шт |
| **stock** | число | ✅ Да | Количество на складе | 10, 0, 100 |
| **image_url** | текст | ❌ Нет | URL изображения (поддерживается Google Drive) | https://drive.google.com/... |

**Важные правила:**

**\* Колонка `size_or_weight`:**
- Для товаров в "кг": вес упаковки в килограммах (например, 2.5 для упаковки 2.5кг)
- Для товаров в "шт":
  - Если < 30: объем в литрах (например, 0.5 для бутылки 0.5л)
  - Если ≥ 30: вес в граммах (например, 250 для упаковки 250г)

**\*\* Колонка `price`:**
- Для товаров в "кг": цена за 1 килограмм
- Для товаров в "шт": цена за 1 штуку/упаковку

**Примеры заполнения:**

```
id | brand  | name           | category  | size_or_weight | price | unit_of_measurement | stock
1  | Фермер | Молоко 2.5%    | Продукты  | 1.0           | 35    | л                   | 50
2  | Nike   | Кроссовки      | Обувь     |               | 2500  | шт                  | 10
3  |        | Сыр Гауда      | Продукты  | 0.3           | 450   | кг                  | 5
4  | Lay's  | Чипсы          | Снеки     | 150           | 45    | шт                  | 30
```

**Изображения из Google Drive:**
- Загрузите изображение на Google Drive
- Откройте изображение и нажмите "Поделиться" → "Получить ссылку" → "Доступ для всех, у кого есть ссылка"
- Скопируйте ссылку в колонку `image_url`
- Бот автоматически преобразует ссылку в правильный формат

### 6. Настройка переменных окружения
1. Скопируйте `.env.example` в `.env`:
   ```bash
   cp .env.example .env
   ```
2. Заполните все значения в `.env` файле полученными учетными данными
3. **ВАЖНО**: Файл `.env` и `credentials.json` находятся в `.gitignore` и не должны попадать в репозиторий!

---

## 🚀 Установка и запуск

### Требования
- Python 3.8 или выше
- pip (менеджер пакетов Python)
- Git (для клонирования репозитория)

### Локальный запуск

**1. Клонируйте репозиторий:**
```bash
git clone https://github.com/Vasyl-Ch/telegram_shop_bot.git
cd telegram_shop_bot
```

**2. Создайте виртуальное окружение (рекомендуется):**
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/MacOS
python3 -m venv venv
source venv/bin/activate
```

**3. Установите зависимости:**
```bash
pip install -r requirements.txt
```

**4. Настройте переменные окружения:**
- Скопируйте `.env.example` в `.env`
- Заполните все необходимые переменные (см. раздел "Настройка и получение учетных данных")
- Поместите файл `credentials.json` в корень проекта

**5. Запустите бота:**
```bash
python main.py
```

Вы должны увидеть сообщение:
```
✅ Bot started successfully
✅ GoogleSheetsClient initialized
```

### Запуск в Docker

**1. Убедитесь, что у вас установлен Docker и docker-compose:**
```bash
docker --version
docker-compose --version
```

**2. Настройте переменные окружения:**
- Создайте файл `.env` (см. выше)
- Убедитесь, что файл `credentials.json` находится в корне проекта
- В `.env` измените `JSON_KEY_FILE` на `/app/credentials.json`

**3. Соберите и запустите контейнер:**
```bash
docker-compose up -d
```

**4. Проверьте логи:**
```bash
docker-compose logs -f telegram-bot
```

**5. Остановить бота:**
```bash
docker-compose down
```

**Полезные команды Docker:**
```bash
# Пересборка контейнера после изменений
docker-compose build --no-cache

# Перезапуск контейнера
docker-compose restart

# Просмотр статуса
docker-compose ps

# Удаление контейнера и данных
docker-compose down -v
```

---

**Хочешь такой же крутой бот для своего бизнеса?** 🚀

📩 Пиши мне в [Telegram](https://t.me/Vasilba1025) — помогу настроить и запустить!

⭐ Поставь звездочку репозиторию, если нравится проект!

## License
This project is licensed under the CC BY-NC 4.0 License — see the [LICENSE](LICENSE) file for details.


---

*P.S. Этот бот уже приносит реальную прибыть магазинам! Не упусти возможность автоматизировать свои продажи!* 💸

#TelegramBot #ИнтернетМагазин #Автоматизация #Ecommerce #Python #GoogleSheets #ОнлайнМагазин #Dropshipping #ShopBot #Startup #ПассивныйДоход #Innovation #TechTrends #MakeMoneyOnline
