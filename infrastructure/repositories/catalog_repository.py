"""
Repository for the product catalog.

Wrapper over your existing CatalogLoader.
Adapts it to the Repository interface.

Adapter Pattern Application:
- CatalogLoader works with dictionaries
- CatalogRepository works with Product entities
- Adapter converts between them
"""

from typing import List, Optional
import logging
from functools import lru_cache
from datetime import datetime, timedelta

from domain.entities.product import Product
from infrastructure.external.google_sheets_client import GoogleSheetsClient

logger = logging.getLogger(__name__)


class CatalogRepository:
    """
    Product catalog repository.

    It is not inherited from BaseRepository because it has specific logic:
    - Data from Google Sheets (read-only via API)
    - Update balances (write)
    - Automatic synchronization
    """

    def __init__(self, google_sheets_client: GoogleSheetsClient):
        self._client = google_sheets_client
        self._cache_timestamp = datetime.now()
        self._cache_ttl = timedelta(minutes=5)
        """
        Args:
            google_sheets_client: Client for working with Google Sheets
        """
        logger.info("✅ CatalogRepository initialized")

    def _is_cache_valid(self) -> bool:
        return datetime.now() - self._cache_timestamp < self._cache_ttl

    @lru_cache(maxsize=512)
    def get_by_id(self, product_id: int) -> Optional[Product]:
        """
        Receives the goods by ID.

        Args:
            product_id: Product ID

        Returns:
            Optional[Product]: Item if found
        """
        if not self._is_cache_valid():
            self.get_by_id.cache_clear()

        data = self._client.data.get(product_id)
        if not data:
            return None

        try:
            return Product.from_dict({**data, "id": product_id})
        except Exception as e:
            logger.error(f"Error creating Product from data: {e}")
            return None

    def get_all(self) -> List[Product]:
        """
        Receives all products from the catalog.

        Returns:
            List[Product]: List of all products
        """
        products = []
        for product_id, data in self._client.data.items():
            try:
                product = Product.from_dict({**data, "id": product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def get_by_category(self, category: str) -> List[Product]:
        """
        Receives goods of a certain category.

        Args:
            category: Category name

        Returns:
            List[Product]: List of products in the category
        """
        items = self._client.get_by_category(category)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, "id": product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def get_categories(self) -> List[str]:
        """
        Gets a list of all categories.

        Returns:
            List[str]: List of unique categories
        """
        return self._client.get_categories()

    def search(self, query: str) -> List[Product]:
        """
        Search for products by name.

        Args:
            query: Search query

        Returns:
            List[Product]: Products found
        """
        items = self._client.search_items(query)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, "id": product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def reduce_stock(self, product_id: int, quantity: int) -> bool:
        """
        Reduces the balance of goods.

        Args:
            product_id: Product ID
            quantity: Quantity to be written off

        Returns:
            bool: True if successful
        """
        try:
            success = self._client.reduce_stock(product_id, quantity)
            if success:
                logger.info(f"📦 Stock reduced: Product #{product_id}, qty: {quantity}")

                product = self.get_by_id(product_id)
                if product and product.stock > 0 and product.stock <= 5:
                    logger.info(
                        f"⚠️ Low stock detected for product #{product_id}: {product.stock} left"
                    )

            return success
        except Exception as e:
            logger.error(f"Error reducing stock: {e}")
            return False

    def is_available(self, product_id: int, quantity: int = 1) -> bool:
        """
        Checks the availability of goods in the required quantity.

        Args:
            product_id: Product ID
            quantity: Required quantity

        Returns:
            bool: True if available
        """
        return self._client.is_available(product_id, quantity)

    def get_stock(self, product_id: int) -> int:
        """
        Receives the current balance of the product.

        Args:
            product_id: Product ID

        Returns:
            int: Stock Balance
        """
        product = self.get_by_id(product_id)
        return product.stock if product else 0

    def reload(self) -> None:
        """
        Force reload directory from Google Sheets.
        """
        try:
            self._client.reload()
            logger.info("🔄 Catalog reloaded from Google Sheets")
        except Exception as e:
            logger.error(f"Error reloading catalog: {e}")

    def get_low_stock_products(self, threshold: int = 5) -> List[Product]:
        """
        Receives goods with a low balance.

        Args:
            threshold: Threshold value

        Returns:
            List[Product]: Products with a balance of <= threshold
        """
        items = self._client.get_low_stock_items(threshold)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, "id": product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products

    def check_and_notify_low_stock(
        self, notification_service, threshold: int = 5
    ) -> None:
        """
        Checks products with low stock and sends notifications.

        Args:
            notification_service: Notification Service
            threshold: Low balance threshold
        """
        low_stock_products = self.get_low_stock_products(threshold)

        for product in low_stock_products:
            notification_service.notify_low_stock(product.name, product.stock)
            logger.info(
                f"⚠️ Low stock notification sent for {product.name} ({product.stock} left)"
            )

    def get_brands(self) -> List[str]:
        """
        Gets a list of all brands.

        Returns:
            List[str]: List of unique brands
        """
        return self._client.get_brands()

    def get_by_brand(self, brand: str) -> List[Product]:
        """
        Receives goods of a certain brand.

        Args:
            brand: Brand name

        Returns:
            List[Product]: List of products with this brand
        """
        items = self._client.get_by_brand(brand)
        products = []

        for product_id, data in items.items():
            try:
                product = Product.from_dict({**data, "id": product_id})
                products.append(product)
            except Exception as e:
                logger.error(f"Error creating Product {product_id}: {e}")

        return products
