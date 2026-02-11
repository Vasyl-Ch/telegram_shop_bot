"""
Базовый абстрактный репозиторий.

Применение SOLID:
- Interface Segregation: минимальный набор методов
- Dependency Inversion: зависимость от абстракции
- Single Responsibility: только CRUD операции

Паттерн Repository:
- Абстрагирует логику хранения данных
- Легко заменить реализацию (in-memory → DB)
- Централизует доступ к данным
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List

# Generic тип для entity
T = TypeVar('T')


class BaseRepository(ABC, Generic[T]):
    """
    Абстрактный базовый репозиторий.

    Generic класс - может работать с любым типом entity.

    Type Parameters:
        T: Тип entity (Order, Cart, Product и т.д.)
    """

    @abstractmethod
    def save(self, entity: T) -> T:
        """
        Сохраняет entity.

        Args:
            entity: Entity для сохранения

        Returns:
            T: Сохраненный entity (с обновленными полями если нужно)
        """
        pass

    @abstractmethod
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """
        Получает entity по ID.

        Args:
            entity_id: Уникальный идентификатор

        Returns:
            Optional[T]: Entity если найден, None иначе
        """
        pass

    @abstractmethod
    def get_all(self) -> List[T]:
        """
        Получает все entity.

        Returns:
            List[T]: Список всех entity
        """
        pass

    @abstractmethod
    def update(self, entity: T) -> T:
        """
        Обновляет существующий entity.

        Args:
            entity: Entity с обновленными данными

        Returns:
            T: Обновленный entity
        """
        pass

    @abstractmethod
    def delete(self, entity_id: int) -> bool:
        """
        Удаляет entity по ID.

        Args:
            entity_id: ID entity для удаления

        Returns:
            bool: True если удален, False если не найден
        """
        pass

    @abstractmethod
    def exists(self, entity_id: int) -> bool:
        """
        Проверяет существование entity.

        Args:
            entity_id: ID entity

        Returns:
            bool: True если существует
        """
        pass