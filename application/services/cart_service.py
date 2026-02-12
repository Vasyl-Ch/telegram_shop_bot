"""
Cart Service — shopping cart management."""

import logging

from domain.entities.cart import Cart, CartItem
from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)


class CartService:
    """
    Cart management service.

    Orchestrates interoperability between Cart, CartRepository
    and CatalogRepository.
    """

    def __init__(
        self,
        cart_repo: CartRepository,
        catalog_repo: CatalogRepository,
    ):
        """
        Args:
            cart_repo: Recycle Bin Repository
            catalog_repo: Directory Repository
        """
        self._cart_repo = cart_repo
        self._catalog_repo = catalog_repo
        logger.info("✅ CartService initialized")

    def get_or_create_cart(self, chat_id: int) -> Cart:
        """
        Retrieves or creates a user's cart.

        Args:
            chat_id: User ID

        Returns:
            Cart: User cart
        """
        return self._cart_repo.get_or_create(chat_id)

    def add_product(self, chat_id: int, product_id: int) -> Cart:
        """
        Adds the product to the cart.

        Args:
            chat_id: User ID
            product_id: Product ID

        Returns:
            Cart: Updated cart

        Raises:
            ValueError: If the product is not found or out of stock
        """
        product = self._catalog_repo.get_by_id(product_id)
        if not product:
            raise ValueError(f"Product #{product_id} not found")

        if not product.is_available:
            raise ValueError(f"Product '{product.name}' is out of stock")

        cart = self._cart_repo.get_or_create(chat_id)
        current_qty = cart.items[product_id].quantity if product_id in cart.items else 0

        if current_qty >= product.stock:
            raise ValueError(f"Cannot add more. Max available: {product.stock}")

        cart_item = CartItem(
            product_id=product.product_id,
            name=product.name,
            price=product.package_price,
            quantity=1,
            max_available=product.stock,
            unit_of_measurement=product.unit_of_measurement,
            size_or_weight=product.size_or_weight,
        )
        cart.add_item(cart_item)
        self._cart_repo.update(cart)

        logger.info(f"🛒 Added product {product_id} to cart {chat_id}")
        return cart

    def remove_product(self, chat_id: int, product_id: int) -> Cart:
        """
        Reduces the number of items in the cart.

        Args:
            chat_id: User ID
            product_id: Product ID

        Returns:
            Cart: Updated cart
        """
        cart = self._cart_repo.get_or_create(chat_id)
        cart.remove_item(product_id)
        self._cart_repo.update(cart)
        return cart

    def clear_cart(self, chat_id: int) -> None:
        """
        Empties the user's Recycle Bin.

        Args:
            chat_id: User ID
        """
        self._cart_repo.clear_cart(chat_id)
        logger.info(f"🗑 Cart cleared for user {chat_id}")

    def validate_cart(self, chat_id: int) -> list[str]:
        """
        Checks the cart against current balances.

        Args:
            chat_id: User ID

        Returns:
            list[str]: List of errors (empty if everything is OK)
        """
        cart = self._cart_repo.get_or_create(chat_id)
        return cart.validate_against_stock(
            lambda pid: self._catalog_repo.get_stock(pid)
        )
