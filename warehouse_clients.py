"""Warehouse API clients for EU (ShipBob) and US (DCL) endpoints."""

import logging

import requests

from config import Config

logger = logging.getLogger(__name__)


class WarehouseClientBase:
    """Base class for warehouse API clients."""

    def __init__(self, base_url: str, api_key: str, live_mode: bool = False):
        self.base_url = base_url
        self.live_mode = live_mode
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        })

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
                "[SIMULATED] Would send order %s to %s\n  Payload: %s",
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

    ShipBob's API expects shipments with a specific schema including
    a reference_id, recipient object, and products array.
    See: https://developer.shipbob.com/
    """

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.EU_WAREHOUSE_URL,
            api_key=config.EU_WAREHOUSE_API_KEY,
            live_mode=config.LIVE_MODE,
        )

    def transform_payload(self, payload: dict) -> dict:
        """Transform generic payload into ShipBob's expected order format."""
        shipping = payload.get("shipping_address") or {}
        return {
            "reference_id": payload.get("order_number", ""),
            "order_number": payload.get("order_number", ""),
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
                    "sku": item["sku"],
                    "name": item["title"],
                    "quantity": item["quantity"],
                }
                for item in payload.get("line_items", [])
            ],
        }


class USWarehouseClient(WarehouseClientBase):
    """Client for the US warehouse (DCL).

    DCL's API expects orders with customer_order_number, ship_to object,
    and an order_lines array with item_number identifiers.
    See: https://api.dclcorp.com/
    """

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.US_WAREHOUSE_URL,
            api_key=config.US_WAREHOUSE_API_KEY,
            live_mode=config.LIVE_MODE,
        )

    def transform_payload(self, payload: dict) -> dict:
        """Transform generic payload into DCL's expected order format."""
        shipping = payload.get("shipping_address") or {}
        return {
            "customer_order_number": payload.get("order_number", ""),
            "ship_to": {
                "email": payload.get("customer_email", ""),
                "address_1": shipping.get("address1", ""),
                "city": shipping.get("city", ""),
                "state": shipping.get("province", ""),
                "country": shipping.get("country", ""),
                "postal_code": shipping.get("zip", ""),
            },
            "order_lines": [
                {
                    "item_number": item["sku"],
                    "description": item["title"],
                    "quantity": item["quantity"],
                }
                for item in payload.get("line_items", [])
            ],
        }
