"""
Google Sheets client (adapter over the existing CatalogLoader).

Adapter Pattern Application:
- Adapts your existing CatalogLoader to the new architecture
- Minimal changes to existing code
- Isolates dependency on the Google Sheets API
"""

import pandas as pd
import logging
from threading import Lock
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)


class GoogleSheetsClient:
    """
        Client for working with Google Sheets.

    Wrapper over your CatalogLoader with minimal changes.
    """

    def __init__(self, google_disk_id: str, json_key_file: str):
        """
        Args:
            google_disk_id: Google Spreadsheet ID
            json_key_file: Path to the JSON file with credentials
        """
        logger.info(f"🔍 GoogleSheetsClient init - json_key_file: {repr(json_key_file)}")
        self.google_disk_id = google_disk_id
        self.json_key_file = json_key_file
        self.lock = Lock()
        self.last_modified = None
        self.data = {}
        self.sheet = None

        self._authenticate()
        self._load()

        logger.info("✅ GoogleSheetsClient initialized")

    def _authenticate(self):
        """Authentication in the Google Sheets API."""
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]

            creds = Credentials.from_service_account_file(
                self.json_key_file, scopes=scopes
            )

            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.google_disk_id)
            self.sheet = self.spreadsheet.sheet1

            logger.info("✅ Google Sheets authentication successful")

        except Exception as e:
            logger.error(f"❌ Google Sheets authentication error: {e}")
            raise

    def _load(self):
        """Loads data from Google Sheets with normalization."""
        try:
            data = self.sheet.get_all_records()

            if not data:
                logger.warning("⚠️ Google Sheet is empty")
                self.data = {}
                return

            df = pd.DataFrame(data)

            required_columns = ["id", "name", "category", "price", "stock"]
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                raise ValueError(
                    f"Missing required columns: {', '.join(missing_columns)}"
                )

            df = df.fillna(
                {
                    "name": "Без названия",
                    "category": "Разное",
                    "price": 0,
                    "stock": 0,
                    "image_url": "",
                    "brand": "",
                    "size_or_weight": 0,
                    "unit_of_measurement": "шт",
                }
            )

            df["id"] = pd.to_numeric(df["id"], errors="coerce")
            df = df.dropna(subset=["id"])
            df["id"] = df["id"].astype(int)

            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0)
            df["stock"] = (
                pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
            )

            if "size_or_weight" in df.columns:
                df["size_or_weight"] = pd.to_numeric(
                    df["size_or_weight"], errors="coerce"
                )
                df["size_or_weight"] = df["size_or_weight"].where(
                    pd.notna(df["size_or_weight"]), None
                )
            else:
                df["size_or_weight"] = None

            if "unit_of_measurement" in df.columns:
                df["unit_of_measurement"] = (
                    df["unit_of_measurement"].astype(str).str.strip().str.lower()
                )
                df["unit_of_measurement"] = df["unit_of_measurement"].replace(
                    {
                        "кг": "кг",
                        "kg": "кг",
                        "килограмм": "кг",
                        "шт": "шт",
                        "sht": "шт",
                        "штука": "шт",
                        "": "шт",
                    }
                )
                kg_mask = df["unit_of_measurement"] == "кг"
                df.loc[
                    kg_mask
                    & ((df["size_or_weight"].isna()) | (df["size_or_weight"] == 0)),
                    "size_or_weight",
                ] = None
                df.loc[
                    ~df["unit_of_measurement"].isin(["кг", "шт"]), "unit_of_measurement"
                ] = "шт"
            else:
                df["unit_of_measurement"] = "шт"

            df = df.drop_duplicates(subset=["id"], keep="first")
            df = df[df["id"] > 0]

            self.data = df.set_index("id").to_dict("index")
            self.last_modified = datetime.now().timestamp()

            for i, (prod_id, prod_data) in enumerate(list(self.data.items())[:5]):
                logger.info(
                    f"Loaded product {prod_id}: name={prod_data.get('name')}, "
                    f"unit={prod_data.get('unit_of_measurement')}, "
                    f"size={prod_data.get('size_or_weight')}, "
                    f"price={prod_data.get('price')}"
                )

            logger.info(f"✅ Loaded {len(self.data)} products from Google Sheets")

            for i, (prod_id, prod_data) in enumerate(list(self.data.items())[:3]):
                logger.debug(
                    f"Product {prod_id}: unit={prod_data.get('unit_of_measurement')}, "
                    f"size={prod_data.get('size_or_weight')}, "
                    f"price={prod_data.get('price')}"
                )

        except Exception as e:
            logger.error(f"❌ Error loading catalog: {e}")
            if not self.data:
                raise

    def _save_to_google_sheets(self):
        """Protects current data in Google Sheet."""
        try:
            df = pd.DataFrame.from_dict(self.data, orient="index")
            df = df.reset_index().rename(columns={"index": "id"})

            columns_order = [
                "id",
                "brand",
                "name",
                "category",
                "size_or_weight",
                "price",
                "unit_of_measurement",
                "stock",
            ]
            if "image_url" in df.columns:
                columns_order.append("image_url")

            for col in columns_order:
                if col not in df.columns:
                    df[col] = ""

            df = df[columns_order]

            headers = df.columns.tolist()
            values = df.values.tolist()
            all_data = [headers] + values

            self.sheet.clear()
            self.sheet.update(all_data, value_input_option="USER_ENTERED")

            self.last_modified = datetime.now().timestamp()
            logger.info("✅ Data saved to Google Sheets")

        except Exception as e:
            logger.error(f"❌ Error saving to Google Sheets: {e}")
            raise

    def reload(self):
        """Reloads data from Google Sheets."""
        with self.lock:
            try:
                self._load()
                logger.info("🔄 Catalog reloaded")
            except Exception as e:
                logger.error(f"❌ Error reloading catalog: {e}")

    def get_categories(self) -> list:
        """Returns a list of unique categories."""
        if not self.data:
            return []

        categories = {item.get("category", "Разное") for item in self.data.values()}
        return sorted(categories)

    def get_by_category(self, category: str) -> dict:
        """Returns items in the specified category."""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if item_data.get("category", "Разное") == category
        }

    def is_available(self, item_id: int, quantity: int = 1) -> bool:
        """Checks the availability of the product."""
        item = self.data.get(item_id)
        if not item:
            return False
        return item.get("stock", 0) >= quantity

    def reduce_stock(self, item_id: int, qty: int) -> bool:
        """Reduces the stock of goods."""
        with self.lock:
            if item_id not in self.data:
                logger.warning(f"⚠️ Product {item_id} not found")
                return False

            current_stock = self.data[item_id].get("stock", 0)
            if current_stock < qty:
                logger.warning(
                    f"⚠️ Insufficient stock for product {item_id}: "
                    f"requested {qty}, available {current_stock}"
                )
                return False

            original_stock = current_stock
            self.data[item_id]["stock"] = current_stock - qty

            try:
                self._save_to_google_sheets()
                logger.info(
                    f"📦 Reduced stock for product {item_id}: "
                    f"{original_stock} → {current_stock - qty}"
                )
                return True
            except Exception as e:
                self.data[item_id]["stock"] = original_stock
                logger.error(f"❌ Error saving stock changes: {e}")
                return False

    def search_items(self, query: str) -> dict:
        """Search for products by name."""
        query = query.lower().strip()
        if not query:
            return {}

        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if query in item_data.get("name", "").lower()
        }

    def get_low_stock_items(self, threshold: int = 5) -> dict:
        """Returns items with a low balance."""
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if 0 < item_data.get("stock", 0) <= threshold
        }

    def get_brands(self) -> list:
        """
        Returns a list of unique brands.

        Returns:
            list: Sorted list of brand names (excluding empty)
        """
        if not self.data:
            return []

        brands = {
            item.get("brand", "").strip()
            for item in self.data.values()
            if item.get("brand", "").strip()
        }
        return sorted(brands)

    def get_by_brand(self, brand: str) -> dict:
        """
        Returns items of the specified brand.

        Args:
            brand: Brand name

        Returns:
            dict: Products filtered by brand
        """
        return {
            item_id: item_data
            for item_id, item_data in self.data.items()
            if item_data.get("brand", "").strip().lower() == brand.strip().lower()
        }
