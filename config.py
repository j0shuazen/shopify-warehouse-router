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

    # ShipBob (EU warehouse) — POST /2.0/order
    # Docs: https://developer.shipbob.com/
    EU_WAREHOUSE_URL: str = os.getenv(
        "EU_WAREHOUSE_URL", "https://api.shipbob.com/2.0/order"
    )
    EU_WAREHOUSE_API_KEY: str = os.getenv("EU_WAREHOUSE_API_KEY", "")
    SHIPBOB_CHANNEL_ID: str = os.getenv("SHIPBOB_CHANNEL_ID", "")

    # DCL Logistics (US warehouse) — POST /api/v1/batches
    # Docs: https://api.dclcorp.com/Help
    # Auth: HTTP Basic (username:password)
    US_WAREHOUSE_URL: str = os.getenv(
        "US_WAREHOUSE_URL", "https://api.dclcorp.com/api/v1/batches"
    )
    DCL_USERNAME: str = os.getenv("DCL_USERNAME", "")
    DCL_PASSWORD: str = os.getenv("DCL_PASSWORD", "")
    DCL_ACCOUNT_NUMBER: str = os.getenv("DCL_ACCOUNT_NUMBER", "")

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
        if self.LIVE_MODE:
            if not self.EU_WAREHOUSE_API_KEY:
                errors.append("EU_WAREHOUSE_API_KEY is required in live mode")
            if not self.SHIPBOB_CHANNEL_ID:
                errors.append("SHIPBOB_CHANNEL_ID is required in live mode")
            if not self.DCL_USERNAME or not self.DCL_PASSWORD:
                errors.append("DCL_USERNAME and DCL_PASSWORD are required in live mode")
            if not self.DCL_ACCOUNT_NUMBER:
                errors.append("DCL_ACCOUNT_NUMBER is required in live mode")
        return errors
