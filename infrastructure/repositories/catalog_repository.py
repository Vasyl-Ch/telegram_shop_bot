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
        """
        Args:
            google_sheets_client: Client for working with Google Sheets
        """
        self._client = google_sheets_client
        logger.info("✅ CatalogRepository initialized")

    def get_by_id(self, product_id: int) -> Optional[Product]:
        """
        Receives the goods by ID.

        Args:
            product_id: Product ID

        Returns:
            Optional[Product]: Item if found
        """
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
