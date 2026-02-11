"""
Репозиторий для каталога товаров.

Обертка над вашим существующим CatalogLoader.
Адаптирует его к интерфейсу Repository.

Применение Adapter Pattern:
- CatalogLoader работает со словарями
- CatalogRepository работает с Product entities
- Адаптер преобразует между ними
"""

from typing import List, Optional
from decimal import Decimal
import logging

from domain.entities.product import Product
from infrastructure.external.google_sheets_client import GoogleSheetsClient

logger = logging.getLogger(__name__)


class CatalogRepository:
    """
    Репозиторий каталога товаров.

    Не наследуется от BaseRepository, т.к. имеет специфичную логику:
    - Данные из Google Sheets (read-only через API)
    - Обновление остатков (write)
    - Автоматическая синхронизация
    """

    def __init__(self, google_sheets_client: GoogleSheetsClient):
        """
        Args:
            google_sheets_client: Клиент для работы с Google Sheets
        """
        self._client = google_sheets_client
        logger.info("✅ CatalogRepository initialized")

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """
        Получает товар по ID.

        Args:
            product_id: ID товара

        Returns:
            Optional[Product]: Товар если найден
        """
        data = self._client.data.get(product_id)
        if not data:
            return None

        try:
            return Product.from_dict({**data, 'id': product_id})
        except Exception as e:
            logger.error(f"Error creating Product from data: {e}")
            return None

    def get_all(self) -> List[Product]:
        """
        Получает все товары из каталога.

        Returns:
            List[Product]: Список всех товаров
        """
        products = []
        for product_id, data in self._client.data.items():
            try:
                product = Product.from_dict({**data, 'id': product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def get_by_category(self, category: str) -> List[Product]:
        """
        Получает товары определенной категории.

        Args:
            category: Название категории

        Returns:
            List[Product]: Список товаров категории
        """
        items = self._client.get_by_category(category)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, 'id': product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def get_categories(self) -> List[str]:
        """
        Получает список всех категорий.

        Returns:
            List[str]: Список уникальных категорий
        """
        return self._client.get_categories()

    def search(self, query: str) -> List[Product]:
        """
        Поиск товаров по названию.

        Args:
            query: Поисковый запрос

        Returns:
            List[Product]: Найденные товары
        """
        items = self._client.search_items(query)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, 'id': product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def reduce_stock(self, product_id: int, quantity: int) -> bool:
        """
        Уменьшает остаток товара.

        Args:
            product_id: ID товара
            quantity: Количество для списания

        Returns:
            bool: True если успешно
        """
        try:
            success = self._client.reduce_stock(product_id, quantity)
            if success:
                logger.info(
                    f"📦 Stock reduced: Product #{product_id}, qty: {quantity}"
                )
            return success
        except Exception as e:
            logger.error(f"Error reducing stock: {e}")
            return False

    def is_available(self, product_id: int, quantity: int = 1) -> bool:
        """
        Проверяет доступность товара в нужном количестве.

        Args:
            product_id: ID товара
            quantity: Требуемое количество

        Returns:
            bool: True если доступно
        """
        return self._client.is_available(product_id, quantity)

    def get_stock(self, product_id: int) -> int:
        """
        Получает текущий остаток товара.

        Args:
            product_id: ID товара

        Returns:
            int: Остаток на складе
        """
        product = self.get_by_id(product_id)
        return product.stock if product else 0

    def reload(self) -> None:
        """
        Принудительно перезагружает каталог из Google Sheets.
        """
        try:
            self._client.reload()
            logger.info("🔄 Catalog reloaded from Google Sheets")
        except Exception as e:
            logger.error(f"Error reloading catalog: {e}")

    def get_low_stock_products(self, threshold: int = 5) -> List[Product]:
        """
        Получает товары с низким остатком.

        Args:
            threshold: Пороговое значение

        Returns:
            List[Product]: Товары с остатком <= threshold
        """
        items = self._client.get_low_stock_items(threshold)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, 'id': product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products