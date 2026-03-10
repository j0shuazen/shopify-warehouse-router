"""Shopify → Warehouse Router: Main entrypoint.

Fetches orders from Shopify's Admin GraphQL API, determines the correct
warehouse based on SKU prefix rules, and sends (or simulates sending)
the order payload to the appropriate warehouse endpoint.
"""

import logging
import sys

from config import Config
from router import build_warehouse_payload, determine_warehouse
from shopify_client import ShopifyClient
from warehouse_clients import EUWarehouseClient, USWarehouseClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    # Load and validate configuration
    config = Config()
    errors = config.validate()
    if errors:
        for err in errors:
            logger.error("Config error: %s", err)
        logger.error("Set required env vars in .env (see .env.example). Exiting.")
        sys.exit(1)

    mode = "LIVE" if config.LIVE_MODE else "SIMULATION"
    logger.info("Starting Shopify → Warehouse Router (%s mode)", mode)

    # Initialize clients
    shopify = ShopifyClient(config)
    eu_warehouse = EUWarehouseClient(config)
    us_warehouse = USWarehouseClient(config)

    # Fetch orders from Shopify
    try:
        orders = shopify.fetch_orders(max_pages=5)
    except Exception as exc:
        logger.error("Failed to fetch orders from Shopify: %s", exc)
        sys.exit(1)

    if not orders:
        logger.info("No orders found. Nothing to route.")
        return

    # Route each order
    results = {"EU": 0, "US": 0, "UNKNOWN": 0, "errors": 0}

    for order in orders:
        order_name = order["name"]
        destination = determine_warehouse(order["line_items"])

        logger.info(
            "Order %s → %s warehouse (SKUs: %s)",
            order_name,
            destination,
            [li["sku"] for li in order["line_items"]],
        )

        if destination == "UNKNOWN":
            logger.warning(
                "Order %s has no routable SKUs. Skipping warehouse dispatch.",
                order_name,
            )
            results["UNKNOWN"] += 1
            continue

        payload = build_warehouse_payload(order, destination)

        if destination == "EU":
            result = eu_warehouse.send_order(payload)
        else:
            result = us_warehouse.send_order(payload)

        if result["status"] == "error":
            results["errors"] += 1
        else:
            results[destination] += 1

    # Summary
    logger.info(
        "Routing complete — EU: %d, US: %d, Unknown: %d, Errors: %d",
        results["EU"],
        results["US"],
        results["UNKNOWN"],
        results["errors"],
    )


if __name__ == "__main__":
    main()
