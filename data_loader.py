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
            try:
                df = pd.read_excel(self.path, engine='openpyxl')
            except Exception as e:
                logging.error(f"Ошибка чтения Excel файла: {e}")
                raise

            # Проверяем наличие данных
            if df.empty:
                logging.warning(f"Excel файл {self.path} пустой")
                self.data = {}
                return

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
            self.last_modified = current_modified

            logging.info(f"Загружено {len(self.data)} товаров из {self.path}")

        except Exception as e:
            logging.error(f"Ошибка загрузки каталога: {e}")
            if not self.data:  # Если данные еще не загружались
                raise

    def reload(self):
        """Перечитывает Excel при изменении файла"""
        with self.lock:
            try:
                self._load()
            except Exception as e:
                logging.error(f"Ошибка при перезагрузке каталога: {e}")
                # Не поднимаем исключение, чтобы не остановить автоматическое обновление

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
            original_stock = current_stock
            self.data[item_id]['stock'] = current_stock - qty

            # Сохраняем изменения в Excel файл
            try:
                self._save_to_excel()
                logging.info(f"Уменьшен запас товара {item_id} на {qty} единиц")
                return True
            except Exception as e:
                # Откатываем изменения в памяти
                self.data[item_id]['stock'] = original_stock
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

            # Создаем резервную копию перед сохранением
            backup_path = f"{self.path}.backup"
            if os.path.exists(self.path):
                try:
                    import shutil
                    shutil.copy2(self.path, backup_path)
                except Exception as e:
                    logging.warning(f"Не удалось создать резервную копию: {e}")

            # Сохраняем в Excel
            df.to_excel(self.path, index=False, engine='openpyxl')
            self.last_modified = os.path.getmtime(self.path)
            
            # Удаляем старую резервную копию если сохранение прошло успешно
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except:
                    pass

        except Exception as e:
            logging.error(f"Ошибка сохранения в Excel: {e}")
            
            # Пытаемся восстановить из резервной копии
            backup_path = f"{self.path}.backup"
            if os.path.exists(backup_path):
                try:
                    import shutil
                    shutil.copy2(backup_path, self.path)
                    logging.info("Восстановлен файл из резервной копии")
                except Exception as restore_error:
                    logging.error(f"Ошибка восстановления из резервной копии: {restore_error}")
            
            raise

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
                self._save_to_excel()
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
                self._save_to_excel()
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
                self._save_to_excel()
                logging.info(f"Удален товар ID {item_id}: {deleted_item.get('name', 'Без названия')}")
                return True
            except Exception as e:
                # Откатываем изменения
                self.data[item_id] = deleted_item
                logging.error(f"Ошибка удаления товара: {e}")
                return False