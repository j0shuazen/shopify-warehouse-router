"""Warehouse routing logic based on SKU prefix rules."""

import logging
from typing import Literal

logger = logging.getLogger(__name__)

WarehouseDestination = Literal["EU", "US", "UNKNOWN"]


def determine_warehouse(line_items: list[dict]) -> WarehouseDestination:
    """Determine which warehouse should receive an order based on SKU prefixes.

    Rules (evaluated in priority order):
        1. If ANY SKU starts with 'EU-' → route to EU warehouse
        2. Else if ANY SKU starts with 'US-' → route to US warehouse
        3. Otherwise → UNKNOWN (no matching prefix found)

    SKUs that are None or blank are logged as warnings and skipped.
    """
    has_us = False

    for item in line_items:
        sku = item.get("sku")
        if not sku:
            logger.warning(
                "Line item '%s' has no SKU — skipping for routing.",
                item.get("title", "unknown"),
            )
            continue

        sku_upper = sku.upper()
        if sku_upper.startswith("EU-"):
            return "EU"
        if sku_upper.startswith("US-"):
            has_us = True

    if has_us:
        return "US"

    return "UNKNOWN"


def build_warehouse_payload(order: dict, destination: WarehouseDestination) -> dict:
    """Transform a normalized Shopify order into a warehouse-ready payload."""
    return {
        "source": "shopify",
        "destination_warehouse": destination,
        "order_id": order["id"],
        "order_number": order["name"],
        "customer_email": order.get("email"),
        "shipping_address": order.get("shipping_address"),
        "line_items": [
            {
                "sku": item["sku"],
                "title": item["title"],
                "quantity": item["quantity"],
            }
            for item in order["line_items"]
            if item.get("sku")  # Only include items that have SKUs
        ],
    }
