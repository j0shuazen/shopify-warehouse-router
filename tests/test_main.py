"""Tests for the main orchestrator."""

import unittest
from unittest.mock import MagicMock, patch

from config import Config


def _make_config(**overrides):
    config = Config.__new__(Config)
    config.SHOPIFY_STORE_NAME = "test-store"
    config.SHOPIFY_ACCESS_TOKEN = "shpat_test"
    config.SHOPIFY_API_VERSION = "2025-07"
    config.EU_WAREHOUSE_URL = "https://eu.example.com"
    config.EU_WAREHOUSE_API_KEY = "eu-key"
    config.US_WAREHOUSE_URL = "https://us.example.com"
    config.US_WAREHOUSE_API_KEY = "us-key"
    config.LIVE_MODE = False
    config.ORDERS_PER_PAGE = 10
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _make_order(name, skus):
    """Helper to create a normalized order dict."""
    return {
        "id": f"gid://shopify/Order/{name}",
        "name": name,
        "created_at": "2026-01-01T00:00:00Z",
        "email": "test@example.com",
        "fulfillment_status": "UNFULFILLED",
        "shipping_address": {"city": "NYC"},
        "line_items": [
            {"sku": sku, "title": f"Item {sku}", "quantity": 1} for sku in skus
        ],
    }


class TestMainRouting(unittest.TestCase):
    """Integration-style tests for the main routing flow."""

    @patch("main.ShopifyClient")
    @patch("main.EUWarehouseClient")
    @patch("main.USWarehouseClient")
    @patch("main.Config")
    def test_eu_order_routed_to_eu_warehouse(self, MockConfig, MockUS, MockEU, MockShopify):
        MockConfig.return_value = _make_config()
        MockConfig.return_value.validate = MagicMock(return_value=[])

        mock_shopify = MagicMock()
        mock_shopify.fetch_orders.return_value = [_make_order("#1001", ["EU-W-001"])]
        MockShopify.return_value = mock_shopify

        mock_eu = MagicMock()
        mock_eu.send_order.return_value = {"status": "simulated", "order_number": "#1001"}
        MockEU.return_value = mock_eu

        mock_us = MagicMock()
        MockUS.return_value = mock_us

        from main import main
        main()

        mock_eu.send_order.assert_called_once()
        mock_us.send_order.assert_not_called()

    @patch("main.ShopifyClient")
    @patch("main.EUWarehouseClient")
    @patch("main.USWarehouseClient")
    @patch("main.Config")
    def test_us_order_routed_to_us_warehouse(self, MockConfig, MockUS, MockEU, MockShopify):
        MockConfig.return_value = _make_config()
        MockConfig.return_value.validate = MagicMock(return_value=[])

        mock_shopify = MagicMock()
        mock_shopify.fetch_orders.return_value = [_make_order("#1002", ["US-G-001"])]
        MockShopify.return_value = mock_shopify

        mock_eu = MagicMock()
        MockEU.return_value = mock_eu

        mock_us = MagicMock()
        mock_us.send_order.return_value = {"status": "simulated", "order_number": "#1002"}
        MockUS.return_value = mock_us

        from main import main
        main()

        mock_us.send_order.assert_called_once()
        mock_eu.send_order.assert_not_called()

    @patch("main.ShopifyClient")
    @patch("main.EUWarehouseClient")
    @patch("main.USWarehouseClient")
    @patch("main.Config")
    def test_unknown_order_skipped(self, MockConfig, MockUS, MockEU, MockShopify):
        MockConfig.return_value = _make_config()
        MockConfig.return_value.validate = MagicMock(return_value=[])

        mock_shopify = MagicMock()
        mock_shopify.fetch_orders.return_value = [_make_order("#1003", ["AU-X-001"])]
        MockShopify.return_value = mock_shopify

        mock_eu = MagicMock()
        MockEU.return_value = mock_eu
        mock_us = MagicMock()
        MockUS.return_value = mock_us

        from main import main
        main()

        mock_eu.send_order.assert_not_called()
        mock_us.send_order.assert_not_called()

    @patch("main.ShopifyClient")
    @patch("main.EUWarehouseClient")
    @patch("main.USWarehouseClient")
    @patch("main.Config")
    def test_mixed_orders_routed_correctly(self, MockConfig, MockUS, MockEU, MockShopify):
        MockConfig.return_value = _make_config()
        MockConfig.return_value.validate = MagicMock(return_value=[])

        mock_shopify = MagicMock()
        mock_shopify.fetch_orders.return_value = [
            _make_order("#1001", ["EU-W-001"]),
            _make_order("#1002", ["US-G-001"]),
            _make_order("#1003", ["AU-X-001"]),
        ]
        MockShopify.return_value = mock_shopify

        mock_eu = MagicMock()
        mock_eu.send_order.return_value = {"status": "simulated", "order_number": "#1001"}
        MockEU.return_value = mock_eu

        mock_us = MagicMock()
        mock_us.send_order.return_value = {"status": "simulated", "order_number": "#1002"}
        MockUS.return_value = mock_us

        from main import main
        main()

        self.assertEqual(mock_eu.send_order.call_count, 1)
        self.assertEqual(mock_us.send_order.call_count, 1)

    @patch("main.ShopifyClient")
    @patch("main.EUWarehouseClient")
    @patch("main.USWarehouseClient")
    @patch("main.Config")
    def test_no_orders_does_nothing(self, MockConfig, MockUS, MockEU, MockShopify):
        MockConfig.return_value = _make_config()
        MockConfig.return_value.validate = MagicMock(return_value=[])

        mock_shopify = MagicMock()
        mock_shopify.fetch_orders.return_value = []
        MockShopify.return_value = mock_shopify

        mock_eu = MagicMock()
        MockEU.return_value = mock_eu
        mock_us = MagicMock()
        MockUS.return_value = mock_us

        from main import main
        main()

        mock_eu.send_order.assert_not_called()
        mock_us.send_order.assert_not_called()

    @patch("main.Config")
    def test_invalid_config_exits(self, MockConfig):
        MockConfig.return_value = _make_config(SHOPIFY_STORE_NAME="")
        MockConfig.return_value.validate = MagicMock(return_value=["SHOPIFY_STORE_NAME is required"])

        from main import main
        with self.assertRaises(SystemExit) as ctx:
            main()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
