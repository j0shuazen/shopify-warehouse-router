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

    def send_order(self, payload: dict) -> dict:
        """Send an order payload to the warehouse endpoint.

        In live mode, performs an actual POST request.
        In simulation mode (default), logs the payload that would be sent.

        Returns a result dict with status information.
        """
        order_number = payload.get("order_number", "unknown")

        if not self.live_mode:
            logger.info(
                "[SIMULATED] Would send order %s to %s\n  Payload: %s",
                order_number,
                self.base_url,
                payload,
            )
            return {"status": "simulated", "order_number": order_number}

        try:
            response = self.session.post(
                self.base_url, json=payload, timeout=30
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
    """Client for the EU warehouse (ShipBob)."""

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.EU_WAREHOUSE_URL,
            api_key=config.EU_WAREHOUSE_API_KEY,
            live_mode=config.LIVE_MODE,
        )


class USWarehouseClient(WarehouseClientBase):
    """Client for the US warehouse (DCL)."""

    def __init__(self, config: Config):
        super().__init__(
            base_url=config.US_WAREHOUSE_URL,
            api_key=config.US_WAREHOUSE_API_KEY,
            live_mode=config.LIVE_MODE,
        )
