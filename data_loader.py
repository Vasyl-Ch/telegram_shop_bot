import pandas as pd
import logging
import os
from threading import Lock
from datetime import datetime


class CatalogLoader:
    """
    Загружает и хранит в памяти данные каталога из Excel,
    позволяет перезагружать данные и обновлять остатки.
    """

    def __init__(self, path: str):
        self.path = path
        self.lock = Lock()
        self.last_modified = None
        self.data = {}
        self._load()

    def _load(self):
        """Загружает данные из Excel файла"""
        try:
            if not os.path.exists(self.path):
                logging.error(f"Excel файл не найден: {self.path}")
                raise FileNotFoundError(f"Файл {self.path} не найден")

            # Проверяем время модификации файла
            current_modified = os.path.getmtime(self.path)
            if self.last_modified and current_modified == self.last_modified:
                return  # Файл не изменился

            # Ожидается, что Excel-файл содержит колонки:
            # id, name, category, price, stock, image_url
            df = pd.read_excel(self.path, engine='openpyxl')

            # Проверяем наличие обязательных колонок
            required_columns = ['id', 'name', 'category', 'price', 'stock']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Отсутствуют обязательные колонки: {', '.join(missing_columns)}")

            # Заполняем пустые значения
            df = df.fillna({
                'name': 'Без названия',
                'category': 'Разное',
                'price': 0,
                'stock': 0,
                'image_url': ''
            })

            # Проверяем типы данных
            df['id'] = df['id'].astype(int)
            df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
            df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)

            # Переводим в словарь вида {id: {name:…, category:…, …}}
            self.data = df.set_index('id').to_dict('index')
            self.last_modified = current_modified

            logging.info(f"Загружено {len(self.data)} товаров из {self.path}")

        except Exception as e:
            logging.error(f"Ошибка загрузки каталога: {e}")
            if not self.data:  # Если данные еще не загружались
                raise

    def reload(self):
        """Перечитывает Excel при изменении файла"""
        with self.lock:
            self._load()

    def get_categories(self) -> list:
        """Возвращает список уникальных категорий"""
        if not self.data:
            return []

        categories = {item.get('category', 'Разное') for item in self.data.values()}
        return sorted(categories)

    def get_by_category(self, category: str) -> dict:
        """Возвращает все товары в указанной категории"""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if item_data.get('category', 'Разное') == category
        }

    def get_item(self, item_id: int) -> dict:
        """Возвращает информацию о конкретном товаре"""
        return self.data.get(item_id)

    def is_available(self, item_id: int, quantity: int = 1) -> bool:
        """Проверяет доступность товара в нужном количестве"""
        item = self.get_item(item_id)
        if not item:
            return False
        return item.get('stock', 0) >= quantity

    def reduce_stock(self, item_id: int, qty: int):
        """Уменьшает запас товара и сохраняет изменения в Excel"""
        with self.lock:
            if item_id not in self.data:
                logging.warning(f"Попытка уменьшить запас несуществующего товара: {item_id}")
                return False

            current_stock = self.data[item_id].get('stock', 0)
            if current_stock < qty:
                logging.warning(f"Недостаточно товара {item_id}: запрос {qty}, доступно {current_stock}")
                return False

            # Уменьшаем запас в памяти
            self.data[item_id]['stock'] = current_stock - qty

            # Сохраняем изменения в Excel файл
            try:
                self._save_to_excel()
                logging.info(f"Уменьшен запас товара {item_id} на {qty} единиц")
                return True
            except Exception as e:
                # Откатываем изменения в памяти
                self.data[item_id]['stock'] = current_stock
                logging.error(f"Ошибка сохранения изменений в Excel: {e}")
                return False

    def _save_to_excel(self):
        """Сохраняет текущие данные в Excel файл"""
        try:
            # Создаем DataFrame из текущих данных
            df = pd.DataFrame.from_dict(self.data, orient='index')
            df = df.reset_index().rename(columns={'index': 'id'})

            # Упорядочиваем колонки
            columns_order = ['id', 'name', 'category', 'price', 'stock']
            if 'image_url' in df.columns:
                columns_order.append('image_url')

            # Добавляем недостающие колонки если их нет
            for col in columns_order:
                if col not in df.columns:
                    df[col] = ''

            df = df[columns_order]

            # Сохраняем в Excel
            df.to_excel(self.path, index=False, engine='openpyxl')
            self.last_modified = os.path.getmtime(self.path)

        except Exception as e:
            logging.error(f"Ошибка сохранения в Excel: {e}")
            raise

    def get_stats(self) -> dict:
        """Возвращает статистику по каталогу"""
        if not self.data:
            return {
                'total_items': 0,
                'total_categories': 0,
                'items_in_stock': 0,
                'items_out_of_stock': 0,
                'total_value': 0
            }

        items_in_stock = sum(1 for item in self.data.values() if item.get('stock', 0) > 0)
        items_out_of_stock = len(self.data) - items_in_stock
        total_value = sum(
            item.get('price', 0) * item.get('stock', 0)
            for item in self.data.values()
        )

        return {
            'total_items': len(self.data),
            'total_categories': len(self.get_categories()),
            'items_in_stock': items_in_stock,
            'items_out_of_stock': items_out_of_stock,
            'total_value': total_value,
            'last_updated': datetime.fromtimestamp(self.last_modified).strftime(
                '%Y-%m-%d %H:%M:%S') if self.last_modified else 'Никогда'
        }

    def search_items(self, query: str) -> dict:
        """Поиск товаров по названию"""
        query = query.lower().strip()
        if not query:
            return {}

        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if query in item_data.get('name', '').lower()
        }

    def get_low_stock_items(self, threshold: int = 5) -> dict:
        """Возвращает товары с низким остатком"""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if 0 < item_data.get('stock', 0) <= threshold
        }

    def validate_data(self) -> list:
        """Проверяет данные на корректность и возвращает список ошибок"""
        errors = []

        for item_id, item_data in self.data.items():
            # Проверяем ID
            if not isinstance(item_id, int) or item_id <= 0:
                errors.append(f"Некорректный ID товара: {item_id}")

            # Проверяем название
            if not item_data.get('name', '').strip():
                errors.append(f"Пустое название для товара ID {item_id}")

            # Проверяем цену
            price = item_data.get('price', 0)
            if not isinstance(price, (int, float)) or price < 0:
                errors.append(f"Некорректная цена для товара ID {item_id}: {price}")

            # Проверяем остаток
            stock = item_data.get('stock', 0)
            if not isinstance(stock, int) or stock < 0:
                errors.append(f"Некорректный остаток для товара ID {item_id}: {stock}")

        return errors