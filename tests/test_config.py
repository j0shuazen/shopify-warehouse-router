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
        config.EU_WAREHOUSE_URL = "https://eu.example.com"
        config.EU_WAREHOUSE_API_KEY = "eu-key"
        config.US_WAREHOUSE_URL = "https://us.example.com"
        config.US_WAREHOUSE_API_KEY = "us-key"
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

    def test_validate_missing_both(self):
        config = self._make_config(SHOPIFY_STORE_NAME="", SHOPIFY_ACCESS_TOKEN="")
        errors = config.validate()
        self.assertEqual(len(errors), 2)

    def test_default_orders_per_page(self):
        config = self._make_config()
        self.assertEqual(config.ORDERS_PER_PAGE, 50)

    def test_default_live_mode_false(self):
        config = self._make_config()
        self.assertFalse(config.LIVE_MODE)


if __name__ == "__main__":
    unittest.main()
