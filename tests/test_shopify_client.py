"""Comprehensive tests for the Shopify GraphQL client."""

import unittest
from unittest.mock import MagicMock, patch

from config import Config
from shopify_client import ShopifyClient


def _make_config(**overrides):
    config = Config.__new__(Config)
    config.SHOPIFY_STORE_NAME = "test-store"
    config.SHOPIFY_ACCESS_TOKEN = "shpat_test_token"
    config.SHOPIFY_API_VERSION = "2025-07"
    config.ORDERS_PER_PAGE = 10
    for k, v in overrides.items():
        setattr(config, k, v)
    return config


def _graphql_response(order_nodes, has_next_page=False, end_cursor=None):
    """Build a mock Shopify GraphQL response."""
    edges = []
    for node in order_nodes:
        edges.append({"node": node})
    return {
        "data": {
            "orders": {
                "edges": edges,
                "pageInfo": {
                    "hasNextPage": has_next_page,
                    "endCursor": end_cursor,
                },
            }
        }
    }


def _make_order_node(order_id="gid://shopify/Order/1", name="#1001",
                     line_items=None, email="test@example.com"):
    """Build a raw GraphQL order node."""
    if line_items is None:
        line_items = [{"title": "Widget", "sku": "EU-W-001", "quantity": 1, "variant": None}]
    return {
        "id": order_id,
        "name": name,
        "createdAt": "2026-01-15T10:00:00Z",
        "email": email,
        "displayFulfillmentStatus": "UNFULFILLED",
        "shippingAddress": {"address1": "1 Main St", "city": "NYC", "province": "NY", "country": "US", "zip": "10001"},
        "lineItems": {
            "edges": [{"node": li} for li in line_items],
        },
    }


class TestShopifyClientInit(unittest.TestCase):
    """Tests for ShopifyClient initialization."""

    def test_session_headers_set(self):
        config = _make_config()
        client = ShopifyClient(config)
        self.assertEqual(client.session.headers["X-Shopify-Access-Token"], "shpat_test_token")
        self.assertEqual(client.session.headers["Content-Type"], "application/json")

    def test_graphql_url(self):
        config = _make_config()
        self.assertEqual(
            config.shopify_graphql_url,
            "https://test-store.myshopify.com/admin/api/2025-07/graphql.json",
        )


class TestResolveSku(unittest.TestCase):
    """Tests for ShopifyClient._resolve_sku()."""

    def test_uses_line_item_sku(self):
        result = ShopifyClient._resolve_sku({"sku": "EU-W-001", "variant": {"sku": "VARIANT-SKU"}})
        self.assertEqual(result, "EU-W-001")

    def test_falls_back_to_variant_sku(self):
        result = ShopifyClient._resolve_sku({"sku": None, "variant": {"sku": "VARIANT-SKU"}})
        self.assertEqual(result, "VARIANT-SKU")

    def test_falls_back_to_variant_sku_when_blank(self):
        result = ShopifyClient._resolve_sku({"sku": "  ", "variant": {"sku": "VARIANT-SKU"}})
        self.assertEqual(result, "VARIANT-SKU")

    def test_returns_none_when_both_missing(self):
        result = ShopifyClient._resolve_sku({"sku": None, "variant": None})
        self.assertIsNone(result)

    def test_returns_none_when_no_variant(self):
        result = ShopifyClient._resolve_sku({"sku": None})
        self.assertIsNone(result)

    def test_returns_none_when_variant_sku_blank(self):
        result = ShopifyClient._resolve_sku({"sku": "", "variant": {"sku": "  "}})
        self.assertIsNone(result)

    def test_strips_whitespace(self):
        result = ShopifyClient._resolve_sku({"sku": "  EU-W-001  ", "variant": None})
        self.assertEqual(result, "EU-W-001")

    def test_variant_sku_stripped(self):
        result = ShopifyClient._resolve_sku({"sku": None, "variant": {"sku": " US-G-002 "}})
        self.assertEqual(result, "US-G-002")


class TestNormalizeOrder(unittest.TestCase):
    """Tests for ShopifyClient._normalize_order()."""

    def setUp(self):
        self.client = ShopifyClient(_make_config())

    def test_basic_normalization(self):
        node = _make_order_node()
        result = self.client._normalize_order(node)
        self.assertEqual(result["id"], "gid://shopify/Order/1")
        self.assertEqual(result["name"], "#1001")
        self.assertEqual(result["created_at"], "2026-01-15T10:00:00Z")
        self.assertEqual(result["email"], "test@example.com")
        self.assertEqual(result["fulfillment_status"], "UNFULFILLED")
        self.assertIsNotNone(result["shipping_address"])
        self.assertEqual(len(result["line_items"]), 1)

    def test_line_item_sku_resolved(self):
        node = _make_order_node(line_items=[
            {"title": "A", "sku": "EU-A", "quantity": 2, "variant": None},
        ])
        result = self.client._normalize_order(node)
        self.assertEqual(result["line_items"][0]["sku"], "EU-A")
        self.assertEqual(result["line_items"][0]["quantity"], 2)

    def test_variant_fallback(self):
        node = _make_order_node(line_items=[
            {"title": "A", "sku": None, "quantity": 1, "variant": {"sku": "US-V-001"}},
        ])
        result = self.client._normalize_order(node)
        self.assertEqual(result["line_items"][0]["sku"], "US-V-001")

    def test_missing_optional_fields(self):
        node = _make_order_node(email=None)
        node["shippingAddress"] = None
        result = self.client._normalize_order(node)
        self.assertIsNone(result["email"])
        self.assertIsNone(result["shipping_address"])

    def test_multiple_line_items(self):
        node = _make_order_node(line_items=[
            {"title": "A", "sku": "EU-A", "quantity": 1, "variant": None},
            {"title": "B", "sku": "US-B", "quantity": 3, "variant": None},
            {"title": "C", "sku": None, "quantity": 1, "variant": None},
        ])
        result = self.client._normalize_order(node)
        self.assertEqual(len(result["line_items"]), 3)
        self.assertEqual(result["line_items"][0]["sku"], "EU-A")
        self.assertEqual(result["line_items"][1]["sku"], "US-B")
        self.assertIsNone(result["line_items"][2]["sku"])


class TestFetchOrders(unittest.TestCase):
    """Tests for ShopifyClient.fetch_orders() with mocked HTTP."""

    def setUp(self):
        self.config = _make_config()
        self.client = ShopifyClient(self.config)

    @patch.object(ShopifyClient, "_execute_query")
    def test_single_page(self, mock_query):
        node = _make_order_node()
        mock_query.return_value = _graphql_response([node])["data"]

        orders = self.client.fetch_orders()
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0]["name"], "#1001")
        mock_query.assert_called_once()

    @patch.object(ShopifyClient, "_execute_query")
    def test_multiple_pages(self, mock_query):
        page1 = _graphql_response(
            [_make_order_node(order_id="gid://shopify/Order/1", name="#1001")],
            has_next_page=True, end_cursor="cursor_abc",
        )["data"]
        page2 = _graphql_response(
            [_make_order_node(order_id="gid://shopify/Order/2", name="#1002")],
            has_next_page=False,
        )["data"]
        mock_query.side_effect = [page1, page2]

        orders = self.client.fetch_orders()
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[0]["name"], "#1001")
        self.assertEqual(orders[1]["name"], "#1002")
        self.assertEqual(mock_query.call_count, 2)

        # Verify cursor was passed on second call
        second_call_vars = mock_query.call_args_list[1][1].get("variables") or mock_query.call_args_list[1][0][1]
        self.assertEqual(second_call_vars["after"], "cursor_abc")

    @patch.object(ShopifyClient, "_execute_query")
    def test_max_pages_limit(self, mock_query):
        page = _graphql_response(
            [_make_order_node()], has_next_page=True, end_cursor="cursor_abc"
        )["data"]
        mock_query.return_value = page

        orders = self.client.fetch_orders(max_pages=1)
        self.assertEqual(len(orders), 1)
        mock_query.assert_called_once()

    @patch.object(ShopifyClient, "_execute_query")
    def test_empty_result(self, mock_query):
        mock_query.return_value = _graphql_response([])["data"]

        orders = self.client.fetch_orders()
        self.assertEqual(orders, [])

    @patch.object(ShopifyClient, "_execute_query")
    def test_default_query_filter_is_paid(self, mock_query):
        """By default, fetch_orders passes financial_status:paid query filter."""
        mock_query.return_value = _graphql_response([])["data"]

        self.client.fetch_orders()
        call_vars = mock_query.call_args[1].get("variables") or mock_query.call_args[0][1]
        self.assertEqual(call_vars["query"], "financial_status:paid")

    @patch.object(ShopifyClient, "_execute_query")
    def test_custom_query_filter(self, mock_query):
        mock_query.return_value = _graphql_response([])["data"]

        self.client.fetch_orders(query="fulfillment_status:unshipped")
        call_vars = mock_query.call_args[1].get("variables") or mock_query.call_args[0][1]
        self.assertEqual(call_vars["query"], "fulfillment_status:unshipped")

    @patch.object(ShopifyClient, "_execute_query")
    def test_none_query_filter_omitted(self, mock_query):
        mock_query.return_value = _graphql_response([])["data"]

        self.client.fetch_orders(query=None)
        call_vars = mock_query.call_args[1].get("variables") or mock_query.call_args[0][1]
        self.assertNotIn("query", call_vars)


class TestExecuteQuery(unittest.TestCase):
    """Tests for ShopifyClient._execute_query() retry and error handling."""

    def setUp(self):
        self.config = _make_config()
        self.client = ShopifyClient(self.config)
        self.client.BASE_BACKOFF_SECONDS = 0.01  # Speed up retries in tests

    @patch("shopify_client.time.sleep")
    @patch("shopify_client.requests.Session.post")
    def test_successful_request(self, mock_post, mock_sleep):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": {"orders": []}}
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # Need to re-create client after patching Session
        client = ShopifyClient(self.config)
        client.session.post = mock_post

        result = client._execute_query("{ orders { edges { node { id } } } }")
        self.assertEqual(result, {"orders": []})
        mock_sleep.assert_not_called()

    @patch("shopify_client.time.sleep")
    def test_http_429_retry(self, mock_sleep):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "0.01"}

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {"data": {"orders": []}}
        mock_ok.raise_for_status = MagicMock()

        self.client.session.post = MagicMock(side_effect=[mock_429, mock_ok])
        result = self.client._execute_query("{ test }")
        self.assertEqual(result, {"orders": []})
        self.assertEqual(self.client.session.post.call_count, 2)

    @patch("shopify_client.time.sleep")
    def test_graphql_throttled_retry(self, mock_sleep):
        throttled_response = MagicMock()
        throttled_response.status_code = 200
        throttled_response.raise_for_status = MagicMock()
        throttled_response.json.return_value = {
            "errors": [{"message": "Throttled", "extensions": {"code": "THROTTLED"}}]
        }

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {"data": {"result": "ok"}}

        self.client.session.post = MagicMock(side_effect=[throttled_response, ok_response])
        result = self.client._execute_query("{ test }")
        self.assertEqual(result, {"result": "ok"})

    @patch("shopify_client.time.sleep")
    def test_graphql_error_raises_after_max_retries(self, mock_sleep):
        error_response = MagicMock()
        error_response.status_code = 200
        error_response.raise_for_status = MagicMock()
        error_response.json.return_value = {
            "errors": [{"message": "Some error", "extensions": {"code": "INTERNAL_ERROR"}}]
        }
        self.client.session.post = MagicMock(return_value=error_response)

        with self.assertRaises(RuntimeError) as ctx:
            self.client._execute_query("{ test }")
        self.assertIn("Shopify GraphQL errors", str(ctx.exception))

    @patch("shopify_client.time.sleep")
    def test_network_error_retries_then_raises(self, mock_sleep):
        import requests as req
        self.client.session.post = MagicMock(
            side_effect=req.exceptions.ConnectionError("Connection refused")
        )

        with self.assertRaises(req.exceptions.ConnectionError):
            self.client._execute_query("{ test }")
        self.assertEqual(self.client.session.post.call_count, self.client.MAX_RETRIES)

    @patch("shopify_client.time.sleep")
    def test_network_error_recovers_on_retry(self, mock_sleep):
        import requests as req

        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {"data": {"ok": True}}

        self.client.session.post = MagicMock(side_effect=[
            req.exceptions.ConnectionError("fail"),
            ok_response,
        ])
        result = self.client._execute_query("{ test }")
        self.assertEqual(result, {"ok": True})

    @patch("shopify_client.time.sleep")
    def test_http_429_exhausts_retries(self, mock_sleep):
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {"Retry-After": "0.01"}

        self.client.session.post = MagicMock(return_value=mock_429)

        with self.assertRaises(RuntimeError) as ctx:
            self.client._execute_query("{ test }")
        self.assertIn("Max retries exceeded", str(ctx.exception))

    @patch("shopify_client.time.sleep")
    def test_variables_passed_in_payload(self, mock_sleep):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {"data": {"ok": True}}
        self.client.session.post = MagicMock(return_value=ok_response)

        self.client._execute_query("{ test }", variables={"first": 10, "after": "abc"})
        call_kwargs = self.client.session.post.call_args
        sent_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        self.assertEqual(sent_json["variables"], {"first": 10, "after": "abc"})

    @patch("shopify_client.time.sleep")
    def test_non_json_response_raises_runtime_error(self, mock_sleep):
        """If Shopify returns non-JSON (e.g. HTML on a 502), raise a clear error."""
        bad_response = MagicMock()
        bad_response.status_code = 200
        bad_response.raise_for_status = MagicMock()
        bad_response.json.side_effect = ValueError("No JSON object could be decoded")
        bad_response.text = "<html>Bad Gateway</html>"
        self.client.session.post = MagicMock(return_value=bad_response)

        with self.assertRaises(RuntimeError) as ctx:
            self.client._execute_query("{ test }")
        self.assertIn("non-JSON response", str(ctx.exception))
        self.assertIn("Bad Gateway", str(ctx.exception))

    @patch("shopify_client.time.sleep")
    def test_no_variables_omitted_from_payload(self, mock_sleep):
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {"data": {"ok": True}}
        self.client.session.post = MagicMock(return_value=ok_response)

        self.client._execute_query("{ test }")
        call_kwargs = self.client.session.post.call_args
        sent_json = call_kwargs[1]["json"] if "json" in call_kwargs[1] else call_kwargs[0][1]
        self.assertNotIn("variables", sent_json)


if __name__ == "__main__":
    unittest.main()
