"""Tests for configuration module."""

import os
import unittest

from config import Config


class TestConfig(unittest.TestCase):
    """Tests for Config class."""

    def _make_config(self, **overrides):
        config = Config.__new__(Config)
        config.SHOPIFY_STORE_NAME = "my-store"
        config.SHOPIFY_ACCESS_TOKEN = "shpat_abc123"
        config.SHOPIFY_API_VERSION = "2025-07"
        config.EU_WAREHOUSE_URL = "https://api.shipbob.com/2.0/order"
        config.EU_WAREHOUSE_API_KEY = "shipbob-pat"
        config.SHIPBOB_CHANNEL_ID = "12345"
        config.US_WAREHOUSE_URL = "https://api.dclcorp.com/api/v1/batches"
        config.DCL_USERNAME = "dcl-user"
        config.DCL_PASSWORD = "dcl-pass"
        config.DCL_ACCOUNT_NUMBER = "ACCT-001"
        config.LIVE_MODE = False
        config.ORDERS_PER_PAGE = 50
        for k, v in overrides.items():
            setattr(config, k, v)
        return config

    def test_graphql_url_format(self):
        config = self._make_config()
        self.assertEqual(
            config.shopify_graphql_url,
            "https://my-store.myshopify.com/admin/api/2025-07/graphql.json",
        )

    def test_graphql_url_with_different_store(self):
        config = self._make_config(SHOPIFY_STORE_NAME="cool-shop")
        self.assertIn("cool-shop.myshopify.com", config.shopify_graphql_url)

    def test_validate_all_present(self):
        config = self._make_config()
        errors = config.validate()
        self.assertEqual(errors, [])

    def test_validate_missing_store_name(self):
        config = self._make_config(SHOPIFY_STORE_NAME="")
        errors = config.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("SHOPIFY_STORE_NAME", errors[0])

    def test_validate_missing_access_token(self):
        config = self._make_config(SHOPIFY_ACCESS_TOKEN="")
        errors = config.validate()
        self.assertEqual(len(errors), 1)
        self.assertIn("SHOPIFY_ACCESS_TOKEN", errors[0])

    def test_validate_missing_both_shopify(self):
        config = self._make_config(SHOPIFY_STORE_NAME="", SHOPIFY_ACCESS_TOKEN="")
        errors = config.validate()
        self.assertEqual(len(errors), 2)

    def test_default_orders_per_page(self):
        config = self._make_config()
        self.assertEqual(config.ORDERS_PER_PAGE, 50)

    def test_default_live_mode_false(self):
        config = self._make_config()
        self.assertFalse(config.LIVE_MODE)

    # --- Live mode credential validation ---

    def test_simulation_mode_skips_warehouse_validation(self):
        """In simulation mode, missing warehouse creds are fine."""
        config = self._make_config(
            EU_WAREHOUSE_API_KEY="", SHIPBOB_CHANNEL_ID="",
            DCL_USERNAME="", DCL_PASSWORD="", DCL_ACCOUNT_NUMBER="",
        )
        errors = config.validate()
        self.assertEqual(errors, [])

    def test_live_mode_requires_shipbob_api_key(self):
        config = self._make_config(LIVE_MODE=True, EU_WAREHOUSE_API_KEY="")
        errors = config.validate()
        self.assertTrue(any("EU_WAREHOUSE_API_KEY" in e for e in errors))

    def test_live_mode_requires_shipbob_channel_id(self):
        config = self._make_config(LIVE_MODE=True, SHIPBOB_CHANNEL_ID="")
        errors = config.validate()
        self.assertTrue(any("SHIPBOB_CHANNEL_ID" in e for e in errors))

    def test_live_mode_requires_dcl_credentials(self):
        config = self._make_config(LIVE_MODE=True, DCL_USERNAME="", DCL_PASSWORD="")
        errors = config.validate()
        self.assertTrue(any("DCL_USERNAME" in e for e in errors))

    def test_live_mode_requires_dcl_account_number(self):
        config = self._make_config(LIVE_MODE=True, DCL_ACCOUNT_NUMBER="")
        errors = config.validate()
        self.assertTrue(any("DCL_ACCOUNT_NUMBER" in e for e in errors))

    def test_live_mode_all_valid(self):
        config = self._make_config(LIVE_MODE=True)
        errors = config.validate()
        self.assertEqual(errors, [])

    # --- Default endpoint URLs ---

    def test_default_eu_url_is_shipbob_order_endpoint(self):
        config = self._make_config()
        self.assertEqual(config.EU_WAREHOUSE_URL, "https://api.shipbob.com/2.0/order")

    def test_default_us_url_is_dcl_batches_endpoint(self):
        config = self._make_config()
        self.assertEqual(config.US_WAREHOUSE_URL, "https://api.dclcorp.com/api/v1/batches")


if __name__ == "__main__":
    unittest.main()
