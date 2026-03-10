"""Comprehensive tests for warehouse client classes."""

import base64
import unittest
from unittest.mock import MagicMock, patch

from config import Config
from warehouse_clients import EUWarehouseClient, USWarehouseClient, WarehouseClientBase


def _make_config(**overrides):
    config = Config.__new__(Config)
    config.EU_WAREHOUSE_URL = "https://api.shipbob.com/2.0/order"
    config.EU_WAREHOUSE_API_KEY = "shipbob-pat-token"
    config.SHIPBOB_CHANNEL_ID = "12345"
    config.US_WAREHOUSE_URL = "https://api.dclcorp.com/api/v1/batches"
    config.DCL_USERNAME = "dcl-user"
    config.DCL_PASSWORD = "dcl-pass"
    config.DCL_ACCOUNT_NUMBER = "ACCT-001"
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
    "shipping_address": {
        "address1": "123 Main St",
        "city": "Berlin",
        "province": "BE",
        "country": "DE",
        "zip": "10115",
    },
    "line_items": [{"sku": "EU-W-001", "title": "Widget", "quantity": 2}],
}


class TestWarehouseClientBaseSimulation(unittest.TestCase):
    """Tests for simulation mode (default)."""

    def test_simulation_returns_simulated_status(self):
        client = WarehouseClientBase("https://example.com", live_mode=False)
        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "simulated")
        self.assertEqual(result["order_number"], "#1001")

    def test_simulation_does_not_make_http_request(self):
        client = WarehouseClientBase("https://example.com", live_mode=False)
        client.session.post = MagicMock()
        client.send_order(SAMPLE_PAYLOAD)
        client.session.post.assert_not_called()

    def test_simulation_with_missing_order_number(self):
        client = WarehouseClientBase("https://example.com", live_mode=False)
        result = client.send_order({"line_items": []})
        self.assertEqual(result["order_number"], "unknown")


class TestWarehouseClientBaseLiveMode(unittest.TestCase):
    """Tests for live mode (actual HTTP calls, mocked)."""

    def test_live_success(self):
        client = WarehouseClientBase("https://example.com", live_mode=True)
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.raise_for_status = MagicMock()
        client.session.post = MagicMock(return_value=mock_response)

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["http_status"], 201)
        self.assertEqual(result["order_number"], "#1001")

    def test_live_http_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.HTTPError("500 Server Error")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("500 Server Error", result["error"])
        self.assertEqual(result["order_number"], "#1001")

    def test_live_connection_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.ConnectionError("Connection refused")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("Connection refused", result["error"])

    def test_live_timeout_error(self):
        import requests
        client = WarehouseClientBase("https://example.com", live_mode=True)
        client.session.post = MagicMock(
            side_effect=requests.exceptions.Timeout("Request timed out")
        )

        result = client.send_order(SAMPLE_PAYLOAD)
        self.assertEqual(result["status"], "error")
        self.assertIn("timed out", result["error"])


class TestBaseTransformPayload(unittest.TestCase):
    """Tests for WarehouseClientBase.transform_payload() (identity)."""

    def test_base_returns_payload_unchanged(self):
        client = WarehouseClientBase("https://example.com")
        self.assertEqual(client.transform_payload(SAMPLE_PAYLOAD), SAMPLE_PAYLOAD)


# --- ShipBob (EU) ---

class TestEUWarehouseClientConfig(unittest.TestCase):
    """Tests for EUWarehouseClient configuration and auth."""

    def test_uses_correct_endpoint(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        self.assertEqual(client.base_url, "https://api.shipbob.com/2.0/order")

    def test_bearer_auth_header(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        self.assertEqual(
            client.session.headers["Authorization"], "Bearer shipbob-pat-token"
        )

    def test_channel_id_header(self):
        config = _make_config()
        client = EUWarehouseClient(config)
        self.assertEqual(client.session.headers["shipbob_channel_id"], "12345")

    def test_live_mode_from_config(self):
        config = _make_config(LIVE_MODE=True)
        client = EUWarehouseClient(config)
        self.assertTrue(client.live_mode)


class TestEUWarehouseClientTransform(unittest.TestCase):
    """Tests for EUWarehouseClient.transform_payload() — ShipBob schema."""

    def setUp(self):
        self.client = EUWarehouseClient(_make_config())

    def test_shipbob_schema_structure(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)

        # ShipBob required fields
        self.assertEqual(result["reference_id"], "gid://shopify/Order/123")
        self.assertEqual(result["order_number"], "#1001")
        self.assertEqual(result["type"], "DTC")
        self.assertEqual(result["shipping_method"], "Standard")
        self.assertIn("recipient", result)
        self.assertIn("products", result)
        self.assertIn("tags", result)

    def test_recipient_mapping(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        recipient = result["recipient"]
        self.assertEqual(recipient["email"], "test@example.com")
        self.assertEqual(recipient["address"]["address1"], "123 Main St")
        self.assertEqual(recipient["address"]["city"], "Berlin")
        self.assertEqual(recipient["address"]["state"], "BE")
        self.assertEqual(recipient["address"]["country"], "DE")
        self.assertEqual(recipient["address"]["zip_code"], "10115")

    def test_products_use_reference_id_for_sku(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        self.assertEqual(len(result["products"]), 1)
        product = result["products"][0]
        self.assertEqual(product["reference_id"], "EU-W-001")
        self.assertEqual(product["name"], "Widget")
        self.assertEqual(product["quantity"], 2)

    def test_tags_include_source(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        self.assertEqual(result["tags"], [{"name": "source", "value": "shopify"}])

    def test_missing_shipping_address(self):
        payload = {**SAMPLE_PAYLOAD, "shipping_address": None}
        result = self.client.transform_payload(payload)
        self.assertEqual(result["recipient"]["address"]["address1"], "")
        self.assertEqual(result["recipient"]["address"]["city"], "")

    def test_empty_line_items(self):
        payload = {**SAMPLE_PAYLOAD, "line_items": []}
        result = self.client.transform_payload(payload)
        self.assertEqual(result["products"], [])


# --- DCL Logistics (US) ---

class TestUSWarehouseClientConfig(unittest.TestCase):
    """Tests for USWarehouseClient configuration and auth."""

    def test_uses_correct_endpoint(self):
        config = _make_config()
        client = USWarehouseClient(config)
        self.assertEqual(client.base_url, "https://api.dclcorp.com/api/v1/batches")

    def test_basic_auth_header(self):
        config = _make_config()
        client = USWarehouseClient(config)
        expected = base64.b64encode(b"dcl-user:dcl-pass").decode()
        self.assertEqual(
            client.session.headers["Authorization"], f"Basic {expected}"
        )

    def test_stores_account_number(self):
        config = _make_config()
        client = USWarehouseClient(config)
        self.assertEqual(client.account_number, "ACCT-001")

    def test_live_mode_from_config(self):
        config = _make_config(LIVE_MODE=True)
        client = USWarehouseClient(config)
        self.assertTrue(client.live_mode)


class TestUSWarehouseClientTransform(unittest.TestCase):
    """Tests for USWarehouseClient.transform_payload() — DCL batch schema."""

    def setUp(self):
        self.client = USWarehouseClient(_make_config())

    def test_dcl_batch_wrapper(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        self.assertFalse(result["allow_partial"])
        self.assertIn("orders", result)
        self.assertEqual(len(result["orders"]), 1)

    def test_order_fields(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        order = result["orders"][0]
        self.assertEqual(order["order_number"], "#1001")
        self.assertEqual(order["account_number"], "ACCT-001")
        self.assertIn("ordered_date", order)
        self.assertEqual(order["shipping_carrier"], "UPS")
        self.assertEqual(order["shipping_service"], "Ground")

    def test_shipping_address_mapping(self):
        result = self.client.transform_payload(SAMPLE_PAYLOAD)
        addr = result["orders"][0]["shipping_address"]
        self.assertEqual(addr["address1"], "123 Main St")
        self.assertEqual(addr["city"], "Berlin")
        self.assertEqual(addr["state_province"], "BE")
        self.assertEqual(addr["postal_code"], "10115")
        self.assertEqual(addr["country_code"], "DE")

    def test_lines_with_sequential_line_numbers(self):
        payload = {
            **SAMPLE_PAYLOAD,
            "line_items": [
                {"sku": "US-A", "title": "Item A", "quantity": 1},
                {"sku": "US-B", "title": "Item B", "quantity": 3},
            ],
        }
        result = self.client.transform_payload(payload)
        lines = result["orders"][0]["lines"]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["line_number"], 1)
        self.assertEqual(lines[0]["item_number"], "US-A")
        self.assertEqual(lines[1]["line_number"], 2)
        self.assertEqual(lines[1]["item_number"], "US-B")
        self.assertEqual(lines[1]["quantity"], 3)

    def test_missing_shipping_address(self):
        payload = {**SAMPLE_PAYLOAD, "shipping_address": None}
        result = self.client.transform_payload(payload)
        addr = result["orders"][0]["shipping_address"]
        self.assertEqual(addr["address1"], "")
        self.assertEqual(addr["city"], "")

    def test_empty_line_items(self):
        payload = {**SAMPLE_PAYLOAD, "line_items": []}
        result = self.client.transform_payload(payload)
        self.assertEqual(result["orders"][0]["lines"], [])


if __name__ == "__main__":
    unittest.main()
