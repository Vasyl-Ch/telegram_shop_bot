import pandas as pd
import logging
import os
from threading import Lock
from datetime import datetime
import gspread  # type: ignore
from google.oauth2.service_account import Credentials  # type: ignore


class CatalogLoader:
    """
    Загружает и хранит в памяти данные каталога из Google Таблицы,
    позволяет перезагружать данные и обновлять остатки.
    """

    def __init__(self, google_disk_id: str, json_key_file: str):
        self.google_disk_id = google_disk_id
        self.json_key_file = json_key_file
        self.lock = Lock()
        self.last_modified = None
        self.data = {}
        self.sheet = None
        self._authenticate()
        self._load()

    def _authenticate(self):
        """Аутентификация в Google Sheets API"""
        try:
            # Определяем область доступа
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # Создаем учетные данные
            creds = Credentials.from_service_account_file(
                self.json_key_file, 
                scopes=scopes
            )
            
            # Авторизуем клиент
            self.client = gspread.authorize(creds)
            
            # Открываем таблицу
            self.spreadsheet = self.client.open_by_key(self.google_disk_id)
            self.sheet = self.spreadsheet.sheet1  # Используем первый лист
            
            logging.info("Успешная аутентификация с Google Таблицами")
            
        except Exception as e:
            logging.error(f"Ошибка аутентификации с Google Таблицами: {e}")
            raise

    def _load(self):
        """Загружает данные из Google Таблицы"""
        try:
            # Получаем все данные из таблицы
            data = self.sheet.get_all_records()
            
            if not data:
                logging.warning("Google Таблица пустая")
                self.data = {}
                return

            # Создаем DataFrame из данных
            df = pd.DataFrame(data)

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

            # Проверяем типы данных и очищаем от некорректных строк
            try:
                df['id'] = pd.to_numeric(df['id'], errors='coerce')
                df = df.dropna(subset=['id'])  # Удаляем строки с некорректным ID
                df['id'] = df['id'].astype(int)
                
                df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0)
                df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)
                
                # Убираем дубликаты по ID
                df = df.drop_duplicates(subset=['id'], keep='first')
                
                # Фильтруем только положительные ID
                df = df[df['id'] > 0]
                
            except Exception as e:
                logging.error(f"Ошибка обработки данных: {e}")
                raise

            # Переводим в словарь вида {id: {name:…, category:…, …}}
            self.data = df.set_index('id').to_dict('index')
            self.last_modified = datetime.now().timestamp()

            logging.info(f"Загружено {len(self.data)} товаров из Google Таблицы")

        except Exception as e:
            logging.error(f"Ошибка загрузки каталога: {e}")
            if not self.data:  # Если данные еще не загружались
                raise

    def _save_to_google_sheets(self):
        """Сохраняет текущие данные в Google Таблицу"""
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

            # Преобразуем DataFrame в список списков для Google Таблицы
            headers = df.columns.tolist()
            values = df.values.tolist()
            all_data = [headers] + values

            # Очищаем лист и записываем новые данные
            self.sheet.clear()
            self.sheet.update(all_data)

            self.last_modified = datetime.now().timestamp()
            logging.info("Данные успешно сохранены в Google Таблицу")

        except Exception as e:
            logging.error(f"Ошибка сохранения в Google Таблицу: {e}")
            raise


    def reload(self):
        """Перечитывает данные из Google Таблицы"""
        with self.lock:
            try:
                self._load()
            except Exception as e:
                logging.error(f"Ошибка при перезагрузке каталога: {e}")


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
        """Уменьшает запас товара и сохраняет изменения в Google Таблицу"""
        with self.lock:
            if item_id not in self.data:
                logging.warning(f"Попытка уменьшить запас несуществующего товара: {item_id}")
                return False

            current_stock = self.data[item_id].get('stock', 0)
            if current_stock < qty:
                logging.warning(f"Недостаточно товара {item_id}: запрос {qty}, доступно {current_stock}")
                return False

            # Уменьшаем запас в памяти
            original_stock = current_stock
            self.data[item_id]['stock'] = current_stock - qty

            # Сохраняем изменения в Google Таблицу
            try:
                self._save_to_google_sheets()
                logging.info(f"Уменьшен запас товара {item_id} на {qty} единиц")
                return True
            except Exception as e:
                # Откатываем изменения в памяти
                self.data[item_id]['stock'] = original_stock
                logging.error(f"Ошибка сохранения изменений в Google Таблицу: {e}")
                return False

    def get_stats(self) -> dict:
        """Возвращает статистику по каталогу"""
        if not self.data:
            return {
                'total_items': 0,
                'total_categories': 0,
                'items_in_stock': 0,
                'items_out_of_stock': 0,
                'total_value': 0,
                'last_updated': 'Никогда'
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

    def add_item(self, name: str, category: str, price: float, stock: int, image_url: str = '') -> int:
        """Добавляет новый товар в каталог"""
        with self.lock:
            # Находим максимальный ID + 1
            max_id = max(self.data.keys()) if self.data else 0
            new_id = max_id + 1
            
            # Добавляем товар
            self.data[new_id] = {
                'name': name,
                'category': category,
                'price': float(price),
                'stock': int(stock),
                'image_url': image_url
            }
            
            try:
                self._save_to_google_sheets()
                logging.info(f"Добавлен новый товар с ID {new_id}: {name}")
                return new_id
            except Exception as e:
                # Откатываем изменения
                del self.data[new_id]
                logging.error(f"Ошибка добавления товара: {e}")
                raise
            
    def update_item(self, item_id: int, **kwargs) -> bool:
        """Обновляет информацию о товаре"""
        with self.lock:
            if item_id not in self.data:
                logging.warning(f"Товар с ID {item_id} не найден")
                return False
            
            # Сохраняем оригинальные данные для отката
            original_data = self.data[item_id].copy()
            
            # Обновляем данные
            allowed_fields = ['name', 'category', 'price', 'stock', 'image_url']
            for field, value in kwargs.items():
                if field in allowed_fields:
                    if field in ['price']:
                        self.data[item_id][field] = float(value)
                    elif field in ['stock']:
                        self.data[item_id][field] = int(value)
                    else:
                        self.data[item_id][field] = str(value)
            
            try:
                self._save_to_google_sheets()
                logging.info(f"Обновлен товар ID {item_id}")
                return True
            except Exception as e:
                # Откатываем изменения
                self.data[item_id] = original_data
                logging.error(f"Ошибка обновления товара: {e}")
                return False

    def delete_item(self, item_id: int) -> bool:
        """Удаляет товар из каталога"""
        with self.lock:
            if item_id not in self.data:
                logging.warning(f"Товар с ID {item_id} не найден")
                return False
            
            # Сохраняем данные для отката
            deleted_item = self.data[item_id].copy()
            
            # Удаляем товар
            del self.data[item_id]
            
            try:
                self._save_to_google_sheets()
                logging.info(f"Удален товар ID {item_id}: {deleted_item.get('name', 'Без названия')}")
                return True
            except Exception as e:
                # Откатываем изменения
                self.data[item_id] = deleted_item
                logging.error(f"Ошибка удаления товара: {e}")
                return False