from __future__ import annotations

import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    SHOPIFY_STORE_NAME: str = os.getenv("SHOPIFY_STORE_NAME", "")
    SHOPIFY_ACCESS_TOKEN: str = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    SHOPIFY_API_VERSION: str = "2025-07"

    EU_WAREHOUSE_URL: str = "https://developer.shipbob.com/api/channels/get-channels"
    EU_WAREHOUSE_API_KEY: str = os.getenv("EU_WAREHOUSE_API_KEY", "")

    US_WAREHOUSE_URL: str = "https://api.dclcorp.com/"
    US_WAREHOUSE_API_KEY: str = os.getenv("US_WAREHOUSE_API_KEY", "")

    LIVE_MODE: bool = os.getenv("LIVE_MODE", "false").lower() == "true"
    ORDERS_PER_PAGE: int = 50

    @property
    def shopify_graphql_url(self) -> str:
        return (
            f"https://{self.SHOPIFY_STORE_NAME}.myshopify.com"
            f"/admin/api/{self.SHOPIFY_API_VERSION}/graphql.json"
        )

    def validate(self) -> list[str]:
        """Return a list of missing required config fields."""
        errors = []
        if not self.SHOPIFY_STORE_NAME:
            errors.append("SHOPIFY_STORE_NAME is required")
        if not self.SHOPIFY_ACCESS_TOKEN:
            errors.append("SHOPIFY_ACCESS_TOKEN is required")
        return errors
