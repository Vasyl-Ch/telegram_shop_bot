"""
Cart Service — управление корзиной покупателя.
"""

import logging
from decimal import Decimal

from domain.entities.cart import Cart, CartItem
from domain.entities.product import Product
from infrastructure.repositories.cart_repository import CartRepository
from infrastructure.repositories.catalog_repository import CatalogRepository

logger = logging.getLogger(__name__)


class CartService:
    """
    Сервис управления корзиной.

    Оркестрирует взаимодействие между Cart, CartRepository
    и CatalogRepository.
    """

    def __init__(
        self,
        cart_repo: CartRepository,
        catalog_repo: CatalogRepository,
    ):
        """
        Args:
            cart_repo: Репозиторий корзин
            catalog_repo: Репозиторий каталога
        """
        self._cart_repo = cart_repo
        self._catalog_repo = catalog_repo
        logger.info("✅ CartService initialized")

    def get_or_create_cart(self, chat_id: int) -> Cart:
        """
        Получает или создаёт корзину пользователя.

        Args:
            chat_id: ID пользователя

        Returns:
            Cart: Корзина пользователя
        """
        return self._cart_repo.get_or_create(chat_id)

    def add_product(self, chat_id: int, product_id: int) -> Cart:
        """
        Добавляет товар в корзину.

        Args:
            chat_id: ID пользователя
            product_id: ID товара

        Returns:
            Cart: Обновлённая корзина

        Raises:
            ValueError: Если товар не найден или нет в наличии
        """
        product = self._catalog_repo.get_by_id(product_id)
        if not product:
            raise ValueError(f"Product #{product_id} not found")

        if not product.is_available:
            raise ValueError(f"Product '{product.name}' is out of stock")

        cart = self._cart_repo.get_or_create(chat_id)
        current_qty = (
            cart.items[product_id].quantity
            if product_id in cart.items
            else 0
        )

        if current_qty >= product.stock:
            raise ValueError(
                f"Cannot add more. Max available: {product.stock}"
            )

        cart_item = CartItem(
            product_id=product.product_id,
            name=product.name,
            price=product.price,
            quantity=1,
            max_available=product.stock,
        )
        cart.add_item(cart_item)
        self._cart_repo.update(cart)

        logger.info(f"🛒 Added product {product_id} to cart {chat_id}")
        return cart

    def remove_product(self, chat_id: int, product_id: int) -> Cart:
        """
        Уменьшает количество товара в корзине.

        Args:
            chat_id: ID пользователя
            product_id: ID товара

        Returns:
            Cart: Обновлённая корзина
        """
        cart = self._cart_repo.get_or_create(chat_id)
        cart.remove_item(product_id)
        self._cart_repo.update(cart)
        return cart

    def clear_cart(self, chat_id: int) -> None:
        """
        Очищает корзину пользователя.

        Args:
            chat_id: ID пользователя
        """
        self._cart_repo.clear_cart(chat_id)
        logger.info(f"🗑 Cart cleared for user {chat_id}")

    def validate_cart(self, chat_id: int) -> list[str]:
        """
        Проверяет корзину против текущих остатков.

        Args:
            chat_id: ID пользователя

        Returns:
            list[str]: Список ошибок (пустой если всё ОК)
        """
        cart = self._cart_repo.get_or_create(chat_id)
        return cart.validate_against_stock(
            lambda pid: self._catalog_repo.get_stock(pid)
        )