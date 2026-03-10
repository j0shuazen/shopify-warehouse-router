# Shopify → Warehouse Router

A Python integration that retrieves orders from Shopify's Admin GraphQL API, applies SKU-based routing rules, and dispatches order payloads to the correct downstream warehouse endpoint.

## Approach

The system is structured as a lightweight middleware pipeline:

1. **Fetch** — `ShopifyClient` queries orders via the Admin GraphQL API using cursor-based pagination. It handles rate limiting (HTTP 429 and GraphQL `THROTTLED` errors) with exponential backoff retries.

2. **Route** — `determine_warehouse()` inspects each order's line item SKUs. If any SKU starts with `EU-`, the order routes to the EU warehouse. Otherwise, if any SKU starts with `US-`, it routes to the US warehouse. EU takes priority per the if/else-if rule structure.

3. **Dispatch** — `EUWarehouseClient` and `USWarehouseClient` each wrap their respective endpoint. In simulation mode (default), they log the payload. In live mode, they POST it.

Each API system (Shopify, EU warehouse, US warehouse) is wrapped in its own class with independent configuration, making it straightforward to swap, extend, or test each integration separately.

## Architecture

```
main.py                          ← Orchestrator / entrypoint
├── config.py                    ← Environment-based configuration
├── shopify_client.py            ← Shopify Admin GraphQL API client
├── router.py                    ← SKU-based routing logic + payload builder
├── warehouse_clients.py         ← EU (ShipBob) + US (DCL) warehouse clients
└── tests/
    ├── test_config.py           ← Config validation tests
    ├── test_router.py           ← Routing logic + payload builder tests
    ├── test_shopify_client.py   ← GraphQL client, pagination, retry tests
    ├── test_warehouse_clients.py← Warehouse dispatch + transform tests
    └── test_main.py             ← End-to-end orchestration tests
```

## Assumptions

- **Authentication**: Shopify access is via a Custom App admin API access token (the `X-Shopify-Access-Token` header approach). The token is provided as an environment variable.
- **API version**: Uses Shopify Admin API version `2025-07`. The GraphQL query structure reflects the real `orders` connection type with `edges`/`node`/`pageInfo` pagination.
- **SKU resolution**: SKU is read from `lineItem.sku` first (the snapshot from order creation), falling back to `lineItem.variant.sku` (the current catalog value). Items with no SKU on either level are logged as warnings and skipped during routing.
- **EU priority**: When an order contains both `EU-` and `US-` prefixed SKUs, the entire order routes to the EU warehouse (per the if/else-if rule structure in the spec).
- **Warehouse endpoints**: Per the assignment, the EU and US endpoints are assumed as given. Payloads are transformed to approximate each vendor's schema (ShipBob-style for EU, DCL-style for US). In a production integration, endpoint paths, auth schemes, and payload contracts would be validated against each vendor's current API documentation. In simulation mode (default), no actual HTTP requests are made.
- **Order page limit**: `main.py` defaults to `max_pages=5` (up to 250 orders per run) as a safety bound. This is configurable — pass a different value to `fetch_orders(max_pages=N)` or `None` to fetch all pages. In production, this would be driven by a CLI flag or environment variable.
- **Line items per order**: The query fetches up to 50 line items per order. Orders exceeding this (uncommon outside B2B) would require inner pagination on the `lineItems` connection. The current implementation does not paginate line items but would log incomplete data if `lineItems.pageInfo.hasNextPage` were checked (a natural next step).

## How to Run

### Prerequisites

- Python 3.9+
- `pip` (or any Python package manager)

### Setup

```bash
cd shopify-warehouse-router

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Shopify store name and access token
```

### Run the router

```bash
python main.py
```

By default, the router runs in **simulation mode** — it fetches orders from Shopify and logs what would be sent to each warehouse without making actual POST requests to the warehouse endpoints.

To enable live dispatch, set `LIVE_MODE=true` in your `.env` file.

### Run tests

```bash
python -m pytest tests/ -v
# or without pytest:
python -m unittest discover -s tests -v
```

## Bonus Features Implemented

- **Pagination**: Cursor-based pagination fetches order pages with a configurable `max_pages` safety limit (default 5 / 250 orders; set to `None` for unlimited)
- **Rate limit handling**: Exponential backoff retry on both HTTP 429 responses and GraphQL `THROTTLED` errors
- **Missing/blank SKU handling**: Logged as warnings, gracefully skipped during routing — never causes a crash
- **Case-insensitive SKU matching**: `eu-widget-001` routes the same as `EU-WIDGET-001`
