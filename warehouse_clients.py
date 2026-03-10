"""Warehouse API clients for EU (ShipBob) and US (DCL Logistics)."""

from __future__ import annotations

import base64
import logging
from datetime import date

import requests

from config import Config

logger = logging.getLogger(__name__)


class WarehouseClientBase:
    """Base class for warehouse API clients."""

    def __init__(self, base_url: str, live_mode: bool = False):
        self.base_url = base_url
        self.live_mode = live_mode
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def _setup_auth(self) -> None:
        """Configure authentication headers. Override in subclasses."""
        pass

    def transform_payload(self, payload: dict) -> dict:
        """Transform a generic warehouse payload into the format expected by this API.

        Subclasses override this to produce endpoint-specific request bodies.
        The base implementation returns the payload unchanged.
        """
        return payload

    def send_order(self, payload: dict) -> dict:
        """Send an order payload to the warehouse endpoint.

        The payload is first transformed via transform_payload() to match the
        target API's expected schema, then either POSTed (live mode) or logged
        (simulation mode).

        Returns a result dict with status information.
        """
        order_number = payload.get("order_number", "unknown")
        transformed = self.transform_payload(payload)

        if not self.live_mode:
            logger.info(
                "[SIMULATED] Would POST order %s to %s\n  Payload: %s",
                order_number,
                self.base_url,
                transformed,
            )
            return {"status": "simulated", "order_number": order_number}

        try:
            response = self.session.post(
                self.base_url, json=transformed, timeout=30
            )
            response.raise_for_status()
            logger.info(
                "Successfully sent order %s to %s (HTTP %d)",
                order_number,
                self.base_url,
                response.status_code,
            )
            return {
                "status": "sent",
                "order_number": order_number,
                "http_status": response.status_code,
            }
        except requests.exceptions.RequestException as exc:
            logger.error(
                "Failed to send order %s to %s: %s",
                order_number,
                self.base_url,
                exc,
            )
            return {
                "status": "error",
                "order_number": order_number,
                "error": str(exc),
            }


class EUWarehouseClient(WarehouseClientBase):
    """Client for the EU warehouse (ShipBob).

    ShipBob order creation endpoint: POST /2.0/order
    Auth: Bearer token (Personal Access Token) + shipbob_channel_id header
    Docs: https://developer.shipbob.com/
    """

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.EU_WAREHOUSE_URL,
            live_mode=config.LIVE_MODE,
        )
        self.session.headers.update({
            "Authorization": f"Bearer {config.EU_WAREHOUSE_API_KEY}",
            "shipbob_channel_id": config.SHIPBOB_CHANNEL_ID,
        })

    def transform_payload(self, payload: dict) -> dict:
        """Transform generic payload into ShipBob's order creation schema.

        ShipBob expects: reference_id (idempotency key), order_number,
        type (DTC/B2B), shipping_method, recipient with address, and
        products matched by reference_id (SKU).
        """
        shipping = payload.get("shipping_address") or {}
        return {
            "reference_id": payload.get("order_id", ""),
            "order_number": payload.get("order_number", ""),
            "type": "DTC",
            "shipping_method": "Standard",
            "recipient": {
                "name": payload.get("customer_email", ""),
                "email": payload.get("customer_email", ""),
                "address": {
                    "address1": shipping.get("address1", ""),
                    "city": shipping.get("city", ""),
                    "state": shipping.get("province", ""),
                    "country": shipping.get("country", ""),
                    "zip_code": shipping.get("zip", ""),
                },
            },
            "products": [
                {
                    "reference_id": item["sku"],
                    "name": item["title"],
                    "quantity": item["quantity"],
                }
                for item in payload.get("line_items", [])
            ],
            "tags": [
                {"name": "source", "value": "shopify"},
            ],
        }


class USWarehouseClient(WarehouseClientBase):
    """Client for the US warehouse (DCL Logistics).

    DCL order submission endpoint: POST /api/v1/batches
    Auth: HTTP Basic Authentication (RFC 2617)
    Orders are submitted in batches (1-1000 orders per request).
    Docs: https://api.dclcorp.com/Help
    """

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.US_WAREHOUSE_URL,
            live_mode=config.LIVE_MODE,
        )
        self.account_number = config.DCL_ACCOUNT_NUMBER
        # DCL uses HTTP Basic Auth (base64-encoded username:password)
        credentials = base64.b64encode(
            f"{config.DCL_USERNAME}:{config.DCL_PASSWORD}".encode()
        ).decode()
        self.session.headers.update({
            "Authorization": f"Basic {credentials}",
        })

    def transform_payload(self, payload: dict) -> dict:
        """Transform generic payload into DCL's batch order schema.

        DCL expects orders submitted in batches via POST /api/v1/batches.
        Each order includes account_number, shipping_address, and lines
        with sequential line_number identifiers.
        """
        shipping = payload.get("shipping_address") or {}
        order = {
            "order_number": payload.get("order_number", ""),
            "account_number": self.account_number,
            "ordered_date": date.today().isoformat(),
            "shipping_carrier": "UPS",
            "shipping_service": "Ground",
            "shipping_address": {
                "attention": payload.get("customer_email", ""),
                "address1": shipping.get("address1", ""),
                "city": shipping.get("city", ""),
                "state_province": shipping.get("province", ""),
                "postal_code": shipping.get("zip", ""),
                "country_code": shipping.get("country", ""),
            },
            "lines": [
                {
                    "line_number": idx + 1,
                    "item_number": item["sku"],
                    "description": item["title"],
                    "quantity": item["quantity"],
                }
                for idx, item in enumerate(payload.get("line_items", []))
            ],
        }
        return {
            "allow_partial": False,
            "orders": [order],
        }
