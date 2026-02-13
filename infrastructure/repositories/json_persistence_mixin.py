"""
Mixin для JSON persistence в репозиториях.
"""

import json
import logging
from pathlib import Path
from typing import TypeVar, Generic, List, Callable
from datetime import datetime
from threading import Lock

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JsonPersistenceMixin(Generic[T]):
    """
    Mixin для автоматического сохранения/загрузки данных в JSON.

    Наследующий класс должен определить:
    - _persistence_file: Path
    - _data: dict[int, T]
    - _lock: Lock
    - _serialize_entity(entity: T) -> dict
    - _deserialize_entity(data: dict) -> T
    """

    def _load_from_disk(self) -> None:
        """Загружает данные из JSON файла."""
        if not hasattr(self, "_persistence_file"):
            raise NotImplementedError("_persistence_file must be defined")

        if not self._persistence_file.exists():
            logger.info(f"📁 No persistence file found at {self._persistence_file}")
            return

        try:
            with open(self._persistence_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            collection_key = self._get_collection_key()
            for item_data in data.get(collection_key, []):
                entity = self._deserialize_entity(item_data)
                entity_id = self._get_entity_id(entity)
                self._data[entity_id] = entity

            logger.info(
                f"✅ Loaded {len(self._data)} items from {self._persistence_file}"
            )

        except Exception as e:
            logger.error(f"❌ Error loading from disk: {e}", exc_info=True)

    def _save_to_disk(self) -> None:
        """Сохраняет данные в JSON файл."""
        try:
            self._persistence_file.parent.mkdir(parents=True, exist_ok=True)

            collection_key = self._get_collection_key()
            data = {
                collection_key: [
                    self._serialize_entity(e) for e in self._data.values()
                ],
                "last_updated": datetime.now().isoformat(),
            }

            temp_file = self._persistence_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            try:
                temp_file.replace(self._persistence_file)
            except PermissionError:
                logger.warning("⚠️ Permission denied, using direct write")
                with open(self._persistence_file, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                try:
                    temp_file.unlink()
                except:
                    pass

            logger.debug(f"💾 Saved {len(self._data)} items to disk")

        except Exception as e:
            logger.error(f"❌ Error saving to disk: {e}", exc_info=True)

    def _get_collection_key(self) -> str:
        """Возвращает ключ коллекции для JSON (переопределить в подклассе)."""
        raise NotImplementedError

    def _serialize_entity(self, entity: T) -> dict:
        """Сериализует сущность в dict (переопределить в подклассе)."""
        raise NotImplementedError

    def _deserialize_entity(self, data: dict) -> T:
        """Десериализует dict в сущность (переопределить в подклассе)."""
        raise NotImplementedError

    def _get_entity_id(self, entity: T) -> int:
        """Получает ID сущности (переопределить в подклассе)."""
        raise NotImplementedError
