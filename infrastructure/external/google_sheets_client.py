"""
Google Sheets клиент (адаптер над существующим CatalogLoader).

Применение Adapter Pattern:
- Адаптирует ваш существующий CatalogLoader к новой архитектуре
- Минимальные изменения в существующем коде
- Изолирует зависимость от Google Sheets API
"""

import pandas as pd
import logging
from threading import Lock
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """
    Клиент для работы с Google Sheets.

    Обертка над вашим CatalogLoader с минимальными изменениями.
    """

    def __init__(self, google_disk_id: str, json_key_file: str):
        """
        Args:
            google_disk_id: ID Google таблицы
            json_key_file: Путь к JSON файлу с credentials
        """
        self.google_disk_id = google_disk_id
        self.json_key_file = json_key_file
        self.lock = Lock()
        self.last_modified = None
        self.data = {}
        self.sheet = None

        self._authenticate()
        self._load()

        logger.info("✅ GoogleSheetsClient initialized")

    def _authenticate(self):
        """Аутентификация в Google Sheets API."""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]

            creds = Credentials.from_service_account_file(
                self.json_key_file,
                scopes=scopes
            )

            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.google_disk_id)
            self.sheet = self.spreadsheet.sheet1

            logger.info("✅ Google Sheets authentication successful")

        except Exception as e:
            logger.error(f"❌ Google Sheets authentication error: {e}")
            raise

    def _load(self):
        """Загружает данные из Google Таблицы."""
        try:
            data = self.sheet.get_all_records()

            if not data:
                logger.warning("⚠️ Google Sheet is empty")
                self.data = {}
                return

            df = pd.DataFrame(data)

            # Проверяем обязательные колонки
            required_columns = ['id', 'name', 'category', 'price', 'stock']
            missing_columns = [
                col for col in required_columns
                if col not in df.columns
            ]

            if missing_columns:
                raise ValueError(
                    f"Missing required columns: {', '.join(missing_columns)}"
                )

            # Заполняем пустые значения
            df = df.fillna({
                'name': 'Без названия',
                'category': 'Разное',
                'price': 0,
                'stock': 0,
                'image_url': ''
            })

            # Очистка и валидация данных
            df['id'] = pd.to_numeric(df['id'], errors='coerce')
            df = df.dropna(subset=['id'])
            df['id'] = df['id'].astype(int)

            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
            df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)

            df = df.drop_duplicates(subset=['id'], keep='first')
            df = df[df['id'] > 0]

            # Переводим в словарь
            self.data = df.set_index('id').to_dict('index')
            self.last_modified = datetime.now().timestamp()

            logger.info(f"✅ Loaded {len(self.data)} products from Google Sheets")

        except Exception as e:
            logger.error(f"❌ Error loading catalog: {e}")
            if not self.data:
                raise

    def _save_to_google_sheets(self):
        """Сохраняет текущие данные в Google Таблицу."""
        try:
            df = pd.DataFrame.from_dict(self.data, orient='index')
            df = df.reset_index().rename(columns={'index': 'id'})

            columns_order = ['id', 'name', 'category', 'price', 'stock']
            if 'image_url' in df.columns:
                columns_order.append('image_url')

            for col in columns_order:
                if col not in df.columns:
                    df[col] = ''

            df = df[columns_order]

            headers = df.columns.tolist()
            values = df.values.tolist()
            all_data = [headers] + values

            self.sheet.clear()
            self.sheet.update(all_data, value_input_option='USER_ENTERED')

            self.last_modified = datetime.now().timestamp()
            logger.info("✅ Data saved to Google Sheets")

        except Exception as e:
            logger.error(f"❌ Error saving to Google Sheets: {e}")
            raise

    def reload(self):
        """Перезагружает данные из Google Sheets."""
        with self.lock:
            try:
                self._load()
                logger.info("🔄 Catalog reloaded")
            except Exception as e:
                logger.error(f"❌ Error reloading catalog: {e}")

    def get_categories(self) -> list:
        """Возвращает список уникальных категорий."""
        if not self.data:
            return []

        categories = {
            item.get('category', 'Разное')
            for item in self.data.values()
        }
        return sorted(categories)

    def get_by_category(self, category: str) -> dict:
        """Возвращает товары в указанной категории."""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if item_data.get('category', 'Разное') == category
        }

    def is_available(self, item_id: int, quantity: int = 1) -> bool:
        """Проверяет доступность товара."""
        item = self.data.get(item_id)
        if not item:
            return False
        return item.get('stock', 0) >= quantity

    def reduce_stock(self, item_id: int, qty: int) -> bool:
        """Уменьшает запас товара."""
        with self.lock:
            if item_id not in self.data:
                logger.warning(f"⚠️ Product {item_id} not found")
                return False

            current_stock = self.data[item_id].get('stock', 0)
            if current_stock < qty:
                logger.warning(
                    f"⚠️ Insufficient stock for product {item_id}: "
                    f"requested {qty}, available {current_stock}"
                )
                return False

            original_stock = current_stock
            self.data[item_id]['stock'] = current_stock - qty

            try:
                self._save_to_google_sheets()
                logger.info(
                    f"📦 Reduced stock for product {item_id}: "
                    f"{original_stock} → {current_stock - qty}"
                )
                return True
            except Exception as e:
                # Откатываем изменения
                self.data[item_id]['stock'] = original_stock
                logger.error(f"❌ Error saving stock changes: {e}")
                return False

    def search_items(self, query: str) -> dict:
        """Поиск товаров по названию."""
        query = query.lower().strip()
        if not query:
            return {}

        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if query in item_data.get('name', '').lower()
        }

    def get_low_stock_items(self, threshold: int = 5) -> dict:
        """Возвращает товары с низким остатком."""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if 0 < item_data.get('stock', 0) <= threshold
        }