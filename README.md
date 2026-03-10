# Shopify → Warehouse Router

A Python integration that retrieves orders from Shopify's Admin GraphQL API, applies SKU-based routing rules, and dispatches order payloads to the correct downstream warehouse endpoint.

## Approach

The system is structured as a lightweight middleware pipeline:

1. **Fetch** — `ShopifyClient` queries orders via the Admin GraphQL API using cursor-based pagination. It filters for paid orders by default and handles rate limiting (HTTP 429 and GraphQL `THROTTLED` errors) with exponential backoff retries.

2. **Route** — `determine_warehouse()` inspects each order's line item SKUs. If any SKU starts with `EU-`, the order routes to the EU warehouse. Otherwise, if any SKU starts with `US-`, it routes to the US warehouse. EU takes priority per the if/else-if rule structure.

3. **Dispatch** — Each warehouse client transforms the generic order payload into the vendor's specific API schema, then POSTs it (live mode) or logs it (simulation mode):
   - **EU → ShipBob** (`POST /2.0/order`): Bearer token auth + `shipbob_channel_id` header. Payload includes `reference_id` (idempotency key), `recipient`, `products` matched by SKU, and `type`/`shipping_method`.
   - **US → DCL Logistics** (`POST /api/v1/batches`): HTTP Basic Auth. Orders submitted in batch format with `account_number`, `shipping_address`, and `lines` with sequential `line_number`.

Each API system (Shopify, ShipBob, DCL) is wrapped in its own class with independent configuration and auth, making it straightforward to swap, extend, or test each integration separately.

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

- **Shopify auth**: Custom App admin API access token (`X-Shopify-Access-Token` header).
- **API version**: Shopify Admin API `2025-07`. The GraphQL query reflects the real `orders` connection type with `edges`/`node`/`pageInfo` pagination.
- **SKU resolution**: Reads `lineItem.sku` first (order-time snapshot), falls back to `variant.sku` (live catalog value). Missing SKUs are logged as warnings and skipped.
- **EU priority**: When an order contains both `EU-` and `US-` prefixed SKUs, the entire order routes to the EU warehouse per the if/else-if spec.
- **ShipBob integration**: Uses the order creation endpoint (`POST /2.0/order`) with Bearer PAT auth and required `shipbob_channel_id` header. Products are matched by `reference_id` (SKU). See [ShipBob API docs](https://developer.shipbob.com/).
- **DCL integration**: Uses the batch order endpoint (`POST /api/v1/batches`) with HTTP Basic Auth (RFC 2617). Orders include `account_number`, carrier/service defaults, and line items with sequential numbering. See [DCL API docs](https://api.dclcorp.com/Help).
- **Order page limit**: `main.py` defaults to `max_pages=5` (up to 250 orders per run) as a safety bound. Configurable via `fetch_orders(max_pages=N)` or `None` for unlimited.
- **Line items per order**: Fetches up to 50 line items per order. Orders exceeding this (uncommon outside B2B) would require inner pagination on the `lineItems` connection — a natural next step.

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
# Edit .env with your credentials (see .env.example for all fields)
```

### Run the router

```bash
python main.py
```

By default, the router runs in **simulation mode** — it fetches orders from Shopify and logs what would be sent to each warehouse without making actual POST requests.

To enable live dispatch, set `LIVE_MODE=true` in your `.env` file. In live mode, ShipBob and DCL warehouse credentials are validated before any API calls are made.

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
