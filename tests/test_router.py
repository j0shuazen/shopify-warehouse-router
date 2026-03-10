"""Unit tests for the warehouse routing logic."""

import unittest

from router import build_warehouse_payload, determine_warehouse


class TestDetermineWarehouse(unittest.TestCase):
    """Tests for determine_warehouse()."""

    def test_eu_sku_routes_to_eu(self):
        items = [{"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_us_sku_routes_to_us(self):
        items = [{"sku": "US-GADGET-002", "title": "Gadget", "quantity": 2}]
        self.assertEqual(determine_warehouse(items), "US")

    def test_eu_takes_priority_over_us(self):
        """If an order has both EU and US SKUs, EU wins (per if/else-if rules)."""
        items = [
            {"sku": "US-GADGET-002", "title": "Gadget", "quantity": 1},
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_no_matching_prefix_returns_unknown(self):
        items = [{"sku": "AU-THING-003", "title": "Thing", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_empty_line_items_returns_unknown(self):
        self.assertEqual(determine_warehouse([]), "UNKNOWN")

    def test_none_sku_is_skipped(self):
        items = [
            {"sku": None, "title": "Mystery Item", "quantity": 1},
            {"sku": "US-GADGET-002", "title": "Gadget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "US")

    def test_blank_sku_is_skipped(self):
        items = [
            {"sku": "", "title": "No SKU Item", "quantity": 1},
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_all_skus_missing_returns_unknown(self):
        items = [
            {"sku": None, "title": "Item A", "quantity": 1},
            {"sku": "", "title": "Item B", "quantity": 2},
        ]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_case_insensitive_matching(self):
        items = [{"sku": "eu-lowercase-001", "title": "Lower", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_us_only_when_no_eu(self):
        """US is only chosen when no EU SKU is present."""
        items = [
            {"sku": "US-ALPHA-001", "title": "Alpha", "quantity": 1},
            {"sku": "US-BETA-002", "title": "Beta", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "US")


class TestBuildWarehousePayload(unittest.TestCase):
    """Tests for build_warehouse_payload()."""

    def test_payload_structure(self):
        order = {
            "id": "gid://shopify/Order/12345",
            "name": "#1001",
            "email": "customer@example.com",
            "shipping_address": {"city": "Berlin", "country": "DE"},
            "line_items": [
                {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 2},
                {"sku": None, "title": "No SKU", "quantity": 1},
            ],
        }

        payload = build_warehouse_payload(order, "EU")

        self.assertEqual(payload["source"], "shopify")
        self.assertEqual(payload["destination_warehouse"], "EU")
        self.assertEqual(payload["order_id"], "gid://shopify/Order/12345")
        self.assertEqual(payload["order_number"], "#1001")
        self.assertEqual(payload["customer_email"], "customer@example.com")
        # Items with no SKU should be excluded from the payload
        self.assertEqual(len(payload["line_items"]), 1)
        self.assertEqual(payload["line_items"][0]["sku"], "EU-WIDGET-001")


if __name__ == "__main__":
    unittest.main()
