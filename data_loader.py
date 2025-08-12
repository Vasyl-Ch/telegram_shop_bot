import pandas as pd
from threading import Lock

class CatalogLoader:
    """
    Загружает и хранит в памяти данные каталога из Excel,
    позволяет перезагружать данные и обновлять остатки.
    """
    def __init__(self, path: str):
        self.path = path
        self.lock = Lock()
        self._load()

    def _load(self):
        # ожидается, что Excel-файл содержит колонки:
        # id, name, category, price, stock, image_url
        df = pd.read_excel(self.path, engine='openpyxl')
        df = df.fillna('')  # на случай пустых ячеек
        # переводим в словарь вида {id: {name:…, category:…, …}}
        self.data = df.set_index('id').to_dict('index')

    def reload(self):
        """Перечитывает Excel при изменении файла."""
        with self.lock:
            self._load()

    def get_categories(self) -> list:
        """Возвращает список уникальных категорий."""
        categories = {item['category'] for item in self.data.values()}
        return sorted(categories)

    def get_by_category(self, category: str) -> dict:
        """Возвращает все товары в указанной категории."""
        return {
            i: d
            for i, d in self.data.items()
            if d.get('category', '') == category
        }

    def reduce_stock(self, item_id, qty: int):
        """Уменьшает запас товара и сохраняет изменения в Excel."""
        with self.lock:
            if item_id in self.data:
                self.data[item_id]['stock'] -= qty
                # Перезаписываем файл
                df = pd.DataFrame.from_dict(self.data, orient='index')
                df.to_excel(self.path, engine='openpyxl')