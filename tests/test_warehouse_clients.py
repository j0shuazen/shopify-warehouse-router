"""Comprehensive tests for warehouse client classes."""

import unittest
from unittest.mock import MagicMock, patch

from config import Config
from warehouse_clients import EUWarehouseClient, USWarehouseClient, WarehouseClientBase


def _make_config(**overrides):
    config = Config.__new__(Config)
    config.EU_WAREHOUSE_URL = "https://eu.example.com/api"
    config.EU_WAREHOUSE_API_KEY = "eu-key-123"
    config.US_WAREHOUSE_URL = "https://us.example.com/api"
    config.US_WAREHOUSE_API_KEY = "us-key-456"
    config.LIVE_MODE = False
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


SAMPLE_PAYLOAD = {
    "source": "shopify",
    "destination_warehouse": "EU",
    "order_id": "gid://shopify/Order/123",
    "order_number": "#1001",
    "customer_email": "test@example.com",
    "shipping_address": {"city": "Berlin"},
    "line_items": [{"sku": "EU-W-001", "title": "Widget", "quantity": 2}],
}


class TestWarehouseClientBaseSimulation(unittest.TestCase):
    """Tests for simulation mode (default)."""

    def test_simulation_returns_simulated_status(self):
        client = WarehouseClientBase("https://example.com", "key", live_mode=False)
        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["order_number"], "#1001")

    def test_simulation_does_not_make_http_request(self):
        client = WarehouseClientBase("https://example.com", "key", live_mode=False)
        client.session.post = MagicMock()
        client.send_order(SAMPLE_PAYLOAD)
        client.session.post.assert_not_called()

    def test_simulation_with_missing_order_number(self):
        client = WarehouseClientBase("https://example.com", "key", live_mode=False)
        result = client.send_order({"line_items": []})
        self.assertEqual(result["order_number"], "unknown")


class TestWarehouseClientBaseLiveMode(unittest.TestCase):
    """Tests for live mode (actual HTTP calls, mocked)."""

    def test_live_success(self):
        client = WarehouseClientBase("https://example.com", "key", live_mode=True)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()
        client.session.post = MagicMock(return_value=mock_response)

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["http_status"], 201)
        self.assertEqual(result["order_number"], "#1001")
        # Base class transform_payload is identity, so payload is unchanged
        client.session.post.assert_called_once_with(
            "https://example.com", json=SAMPLE_PAYLOAD, timeout=30,
        )

    def test_live_http_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", "key", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.HTTPError("500 Server Error")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("500 Server Error", result["error"])
        self.assertEqual(result["order_number"], "#1001")

    def test_live_connection_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", "key", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.ConnectionError("Connection refused")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("Connection refused", result["error"])

    def test_live_timeout_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", "key", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["error"])


class TestWarehouseClientHeaders(unittest.TestCase):
    """Tests for authentication headers."""

    def test_bearer_token_set(self):
        client = WarehouseClientBase("https://example.com", "my-api-key")
        self.assertEqual(client.session.headers["Authorization"], "Bearer my-api-key")
        self.assertEqual(client.session.headers["Content-Type"], "application/json")

    def test_empty_api_key(self):
        client = WarehouseClientBase("https://example.com", "")
        self.assertEqual(client.session.headers["Authorization"], "Bearer ")


class TestBaseTransformPayload(unittest.TestCase):
    """Tests for WarehouseClientBase.transform_payload() (identity)."""

    def test_base_returns_payload_unchanged(self):
        client = WarehouseClientBase("https://example.com", "key")
        self.assertEqual(client.transform_payload(SAMPLE_PAYLOAD), SAMPLE_PAYLOAD)


class TestEUWarehouseClient(unittest.TestCase):
    """Tests for EUWarehouseClient configuration and payload transform."""

    def test_uses_eu_config(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        self.assertEqual(client.base_url, "https://eu.example.com/api")
        self.assertFalse(client.live_mode)

    def test_live_mode_from_config(self):
        config = _make_config(LIVE_MODE=True)
        client = EUWarehouseClient(config)
        self.assertTrue(client.live_mode)

    def test_transform_payload_shipbob_format(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        payload = {
            "order_number": "#1001",
            "customer_email": "test@example.com",
            "shipping_address": {
                "address1": "123 Main St",
                "city": "Berlin",
                "province": "BE",
                "country": "DE",
                "zip": "10115",
            },
            "line_items": [
                {"sku": "EU-W-001", "title": "Widget", "quantity": 2},
            ],
        }
        result = client.transform_payload(payload)

        self.assertEqual(result["reference_id"], "#1001")
        self.assertEqual(result["order_number"], "#1001")
        self.assertEqual(result["recipient"]["email"], "test@example.com")
        self.assertEqual(result["recipient"]["address"]["address1"], "123 Main St")
        self.assertEqual(result["recipient"]["address"]["city"], "Berlin")
        self.assertEqual(result["recipient"]["address"]["country"], "DE")
        self.assertEqual(result["recipient"]["address"]["zip_code"], "10115")
        self.assertEqual(len(result["products"]), 1)
        self.assertEqual(result["products"][0]["sku"], "EU-W-001")
        self.assertEqual(result["products"][0]["name"], "Widget")
        self.assertEqual(result["products"][0]["quantity"], 2)

    def test_transform_payload_missing_shipping(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        payload = {
            "order_number": "#1002",
            "customer_email": "a@b.com",
            "shipping_address": None,
            "line_items": [],
        }
        result = client.transform_payload(payload)
        self.assertEqual(result["recipient"]["address"]["address1"], "")
        self.assertEqual(result["products"], [])


class TestUSWarehouseClient(unittest.TestCase):
    """Tests for USWarehouseClient configuration and payload transform."""

    def test_uses_us_config(self):
        config = _make_config()
        client = USWarehouseClient(config)
        self.assertEqual(client.base_url, "https://us.example.com/api")
        self.assertFalse(client.live_mode)

    def test_live_mode_from_config(self):
        config = _make_config(LIVE_MODE=True)
        client = USWarehouseClient(config)
        self.assertTrue(client.live_mode)

    def test_transform_payload_dcl_format(self):
        config = _make_config()
        client = USWarehouseClient(config)
        payload = {
            "order_number": "#2001",
            "customer_email": "buyer@example.com",
            "shipping_address": {
                "address1": "456 Oak Ave",
                "city": "Chicago",
                "province": "IL",
                "country": "US",
                "zip": "60601",
            },
            "line_items": [
                {"sku": "US-G-001", "title": "Gadget", "quantity": 3},
                {"sku": "US-G-002", "title": "Gizmo", "quantity": 1},
            ],
        }
        result = client.transform_payload(payload)

        self.assertEqual(result["customer_order_number"], "#2001")
        self.assertEqual(result["ship_to"]["email"], "buyer@example.com")
        self.assertEqual(result["ship_to"]["address_1"], "456 Oak Ave")
        self.assertEqual(result["ship_to"]["city"], "Chicago")
        self.assertEqual(result["ship_to"]["state"], "IL")
        self.assertEqual(result["ship_to"]["postal_code"], "60601")
        self.assertEqual(len(result["order_lines"]), 2)
        self.assertEqual(result["order_lines"][0]["item_number"], "US-G-001")
        self.assertEqual(result["order_lines"][0]["description"], "Gadget")
        self.assertEqual(result["order_lines"][1]["quantity"], 1)

    def test_transform_payload_missing_shipping(self):
        config = _make_config()
        client = USWarehouseClient(config)
        payload = {
            "order_number": "#2002",
            "customer_email": "a@b.com",
            "shipping_address": None,
            "line_items": [],
        }
        result = client.transform_payload(payload)
        self.assertEqual(result["ship_to"]["address_1"], "")
        self.assertEqual(result["order_lines"], [])


if __name__ == "__main__":
    unittest.main()
