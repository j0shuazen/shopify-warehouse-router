"""Shopify Admin GraphQL API client for retrieving orders."""

from __future__ import annotations

import logging
import time
from typing import Optional

import requests

from config import Config

logger = logging.getLogger(__name__)

# GraphQL query that fetches orders with line items, SKUs, and pagination support.
# Uses the Shopify Admin GraphQL API connection pattern (edges/node/pageInfo).
ORDERS_QUERY = """
query FetchOrders($first: Int!, $after: String) {
  orders(first: $first, after: $after) {
    edges {
      node {
        id
        name
        createdAt
        email
        displayFulfillmentStatus
        shippingAddress {
          address1
          city
          province
          country
          zip
        }
        lineItems(first: 50) {
          edges {
            node {
              title
              sku
              quantity
              variant {
                sku
              }
            }
          }
        }
      }
    }
    pageInfo {
      hasNextPage
      endCursor
    }
  }
}
"""


class ShopifyClient:
    """Client for the Shopify Admin GraphQL API.

    Handles authentication, pagination, and rate-limit retries.
    """

    MAX_RETRIES = 3
    BASE_BACKOFF_SECONDS = 1.0

    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-Shopify-Access-Token": config.SHOPIFY_ACCESS_TOKEN,
        })

    def _execute_query(self, query: str, variables: dict | None = None) -> dict:
        """Execute a GraphQL query against the Shopify Admin API with retry logic."""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.post(
                    self.config.shopify_graphql_url, json=payload, timeout=30
                )

                # Handle HTTP-level rate limiting (429)
                if response.status_code == 429:
                    retry_after = float(response.headers.get("Retry-After", self.BASE_BACKOFF_SECONDS))
                    logger.warning("Rate limited (429). Retrying in %.1fs...", retry_after)
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                result = response.json()

                # Handle GraphQL-level throttling (Shopify returns errors in the response body)
                if "errors" in result:
                    throttled = any(
                        "THROTTLED" in str(e.get("extensions", {}).get("code", ""))
                        for e in result["errors"]
                    )
                    if throttled and attempt < self.MAX_RETRIES:
                        wait = self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                        logger.warning("GraphQL throttled. Retrying in %.1fs...", wait)
                        time.sleep(wait)
                        continue

                    error_messages = [e.get("message", str(e)) for e in result["errors"]]
                    raise RuntimeError(f"Shopify GraphQL errors: {error_messages}")

                return result["data"]

            except requests.exceptions.RequestException as exc:
                if attempt < self.MAX_RETRIES:
                    wait = self.BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning("Request failed (%s). Retrying in %.1fs...", exc, wait)
                    time.sleep(wait)
                else:
                    raise

        raise RuntimeError("Max retries exceeded for Shopify GraphQL request")

    def fetch_orders(self, max_pages: int | None = None) -> list[dict]:
        """Fetch orders from Shopify using cursor-based pagination.

        Args:
            max_pages: Optional limit on the number of pages to fetch.
                       None means fetch all pages.

        Returns:
            List of order dicts with normalized line item data.
        """
        orders = []
        cursor = None
        page = 0

        while True:
            page += 1
            logger.info("Fetching orders page %d (cursor: %s)", page, cursor or "start")

            variables = {"first": self.config.ORDERS_PER_PAGE}
            if cursor:
                variables["after"] = cursor

            data = self._execute_query(ORDERS_QUERY, variables)
            orders_data = data["orders"]

            for edge in orders_data["edges"]:
                order = self._normalize_order(edge["node"])
                orders.append(order)

            page_info = orders_data["pageInfo"]
            if not page_info["hasNextPage"]:
                break
            if max_pages and page >= max_pages:
                logger.info("Reached max_pages limit (%d). Stopping.", max_pages)
                break

            cursor = page_info["endCursor"]

        logger.info("Fetched %d orders total.", len(orders))
        return orders

    def _normalize_order(self, node: dict) -> dict:
        """Normalize a raw GraphQL order node into a clean dict."""
        line_items = []
        for li_edge in node["lineItems"]["edges"]:
            li = li_edge["node"]
            sku = self._resolve_sku(li)
            line_items.append({
                "title": li["title"],
                "sku": sku,
                "quantity": li["quantity"],
            })

        return {
            "id": node["id"],
            "name": node["name"],
            "created_at": node["createdAt"],
            "email": node.get("email"),
            "fulfillment_status": node.get("displayFulfillmentStatus"),
            "shipping_address": node.get("shippingAddress"),
            "line_items": line_items,
        }

    @staticmethod
    def _resolve_sku(line_item: dict) -> str | None:
        """Resolve the SKU from a line item, falling back to the variant SKU.

        Returns None if no SKU is available on either level.
        """
        sku = line_item.get("sku")
        if sku and sku.strip():
            return sku.strip()

        variant = line_item.get("variant")
        if variant:
            variant_sku = variant.get("sku")
            if variant_sku and variant_sku.strip():
                return variant_sku.strip()

        return None
