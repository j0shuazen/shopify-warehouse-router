"""Comprehensive tests for the warehouse routing logic."""

import unittest

from router import build_warehouse_payload, determine_warehouse


class TestDetermineWarehouse(unittest.TestCase):
    """Tests for determine_warehouse()."""

    # --- Basic routing ---

    def test_eu_sku_routes_to_eu(self):
        items = [{"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_us_sku_routes_to_us(self):
        items = [{"sku": "US-GADGET-002", "title": "Gadget", "quantity": 2}]
        self.assertEqual(determine_warehouse(items), "US")

    def test_no_matching_prefix_returns_unknown(self):
        items = [{"sku": "AU-THING-003", "title": "Thing", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_empty_line_items_returns_unknown(self):
        self.assertEqual(determine_warehouse([]), "UNKNOWN")

    # --- Priority rules ---

    def test_eu_takes_priority_over_us(self):
        """If an order has both EU and US SKUs, EU wins (per if/else-if rules)."""
        items = [
            {"sku": "US-GADGET-002", "title": "Gadget", "quantity": 1},
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_eu_priority_regardless_of_order(self):
        """EU wins even when EU SKU appears first."""
        items = [
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
            {"sku": "US-GADGET-002", "title": "Gadget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_us_only_when_no_eu(self):
        items = [
            {"sku": "US-ALPHA-001", "title": "Alpha", "quantity": 1},
            {"sku": "US-BETA-002", "title": "Beta", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "US")

    def test_mixed_us_and_unroutable_routes_to_us(self):
        items = [
            {"sku": "AU-THING-003", "title": "Thing", "quantity": 1},
            {"sku": "US-GADGET-002", "title": "Gadget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "US")

    def test_mixed_eu_and_unroutable_routes_to_eu(self):
        items = [
            {"sku": "JP-ITEM-001", "title": "Japan Item", "quantity": 1},
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    # --- Missing / blank SKU handling ---

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

    def test_all_skus_none_returns_unknown(self):
        items = [
            {"sku": None, "title": "Item A", "quantity": 1},
            {"sku": None, "title": "Item B", "quantity": 2},
        ]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_all_skus_blank_returns_unknown(self):
        items = [
            {"sku": "", "title": "Item A", "quantity": 1},
            {"sku": "", "title": "Item B", "quantity": 2},
        ]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_mixed_none_and_blank_returns_unknown(self):
        items = [
            {"sku": None, "title": "Item A", "quantity": 1},
            {"sku": "", "title": "Item B", "quantity": 2},
        ]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_missing_sku_key_is_skipped(self):
        """Line item dict without a 'sku' key at all."""
        items = [
            {"title": "No SKU Key", "quantity": 1},
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 1},
        ]
        self.assertEqual(determine_warehouse(items), "EU")

    # --- Case insensitivity ---

    def test_case_insensitive_eu(self):
        items = [{"sku": "eu-lowercase-001", "title": "Lower", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_case_insensitive_us(self):
        items = [{"sku": "us-lowercase-001", "title": "Lower", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "US")

    def test_mixed_case_eu(self):
        items = [{"sku": "Eu-MixedCase-001", "title": "Mixed", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    # --- Edge cases ---

    def test_sku_is_exactly_eu_dash(self):
        """SKU that is literally 'EU-' with nothing after it."""
        items = [{"sku": "EU-", "title": "Minimal", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "EU")

    def test_sku_starts_with_eu_no_dash(self):
        """SKU 'EURO-123' should NOT match EU- prefix."""
        items = [{"sku": "EURO-123", "title": "Euro Item", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_sku_starts_with_us_no_dash(self):
        """SKU 'USA-123' should NOT match US- prefix."""
        items = [{"sku": "USA-123", "title": "USA Item", "quantity": 1}]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_single_item_no_match(self):
        items = [{"sku": "GENERIC-001", "title": "Generic", "quantity": 5}]
        self.assertEqual(determine_warehouse(items), "UNKNOWN")

    def test_large_order_with_many_items(self):
        """Simulates an order with many line items; EU somewhere in the middle."""
        items = [{"sku": f"GEN-{i:04d}", "title": f"Item {i}", "quantity": 1} for i in range(20)]
        items[12] = {"sku": "EU-SPECIAL-012", "title": "Special EU", "quantity": 1}
        self.assertEqual(determine_warehouse(items), "EU")

    def test_large_order_us_only(self):
        items = [{"sku": f"US-ITEM-{i:04d}", "title": f"Item {i}", "quantity": 1} for i in range(15)]
        self.assertEqual(determine_warehouse(items), "US")


class TestBuildWarehousePayload(unittest.TestCase):
    """Tests for build_warehouse_payload()."""

    def _make_order(self, **overrides):
        base = {
            "id": "gid://shopify/Order/12345",
            "name": "#1001",
            "email": "customer@example.com",
            "shipping_address": {"address1": "123 Main St", "city": "Berlin", "country": "DE"},
            "line_items": [
                {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 2},
            ],
        }
        base.update(overrides)
        return base

    def test_payload_has_all_required_fields(self):
        order = self._make_order()
        payload = build_warehouse_payload(order, "EU")

        self.assertEqual(payload["source"], "shopify")
        self.assertEqual(payload["destination_warehouse"], "EU")
        self.assertEqual(payload["order_id"], "gid://shopify/Order/12345")
        self.assertEqual(payload["order_number"], "#1001")
        self.assertEqual(payload["customer_email"], "customer@example.com")
        self.assertIsNotNone(payload["shipping_address"])
        self.assertEqual(len(payload["line_items"]), 1)

    def test_items_without_sku_are_excluded(self):
        order = self._make_order(line_items=[
            {"sku": "EU-WIDGET-001", "title": "Widget", "quantity": 2},
            {"sku": None, "title": "No SKU", "quantity": 1},
            {"sku": "", "title": "Blank SKU", "quantity": 1},
        ])
        payload = build_warehouse_payload(order, "EU")
        self.assertEqual(len(payload["line_items"]), 1)
        self.assertEqual(payload["line_items"][0]["sku"], "EU-WIDGET-001")

    def test_us_destination(self):
        order = self._make_order(line_items=[
            {"sku": "US-GADGET-001", "title": "Gadget", "quantity": 3},
        ])
        payload = build_warehouse_payload(order, "US")
        self.assertEqual(payload["destination_warehouse"], "US")
        self.assertEqual(payload["line_items"][0]["sku"], "US-GADGET-001")

    def test_missing_email_is_none(self):
        order = self._make_order()
        del order["email"]
        payload = build_warehouse_payload(order, "EU")
        self.assertIsNone(payload["customer_email"])

    def test_missing_shipping_address_is_none(self):
        order = self._make_order()
        del order["shipping_address"]
        payload = build_warehouse_payload(order, "EU")
        self.assertIsNone(payload["shipping_address"])

    def test_line_item_fields_preserved(self):
        order = self._make_order(line_items=[
            {"sku": "EU-WIDGET-001", "title": "Widget Pro", "quantity": 7},
        ])
        payload = build_warehouse_payload(order, "EU")
        li = payload["line_items"][0]
        self.assertEqual(li["sku"], "EU-WIDGET-001")
        self.assertEqual(li["title"], "Widget Pro")
        self.assertEqual(li["quantity"], 7)

    def test_multiple_valid_items_all_included(self):
        order = self._make_order(line_items=[
            {"sku": "EU-A", "title": "A", "quantity": 1},
            {"sku": "EU-B", "title": "B", "quantity": 2},
            {"sku": "US-C", "title": "C", "quantity": 3},
        ])
        payload = build_warehouse_payload(order, "EU")
        self.assertEqual(len(payload["line_items"]), 3)

    def test_all_items_no_sku_produces_empty_list(self):
        order = self._make_order(line_items=[
            {"sku": None, "title": "A", "quantity": 1},
            {"sku": "", "title": "B", "quantity": 1},
        ])
        payload = build_warehouse_payload(order, "UNKNOWN")
        self.assertEqual(payload["line_items"], [])


if __name__ == "__main__":
    unittest.main()
