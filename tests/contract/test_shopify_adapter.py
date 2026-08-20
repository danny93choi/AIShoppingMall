import json

import httpx
import pytest
from pydantic import SecretStr

from commerce_agent.integrations.commerce.base import RateLimitError
from commerce_agent.integrations.commerce.shopify import (
    ShopifyCommerceAdapter,
    ShopifyCredentials,
    verify_shopify_webhook,
)


def product_connection() -> dict[str, object]:
    return {
        "products": {
            "edges": [
                {
                    "cursor": "cursor-1",
                    "node": {
                        "id": "gid://shopify/Product/1",
                        "title": "Cup",
                        "description": "Daily cup",
                        "productType": "Drinkware",
                        "status": "ACTIVE",
                        "createdAt": "2026-01-01T00:00:00Z",
                        "updatedAt": "2026-08-01T00:00:00Z",
                        "variants": {
                            "nodes": [
                                {
                                    "price": "20.00",
                                    "inventoryQuantity": 4,
                                    "inventoryItem": {
                                        "unitCost": {"amount": "8.00", "currencyCode": "USD"}
                                    },
                                }
                            ]
                        },
                    },
                }
            ],
            "pageInfo": {"hasNextPage": False, "endCursor": "cursor-1"},
        }
    }


@pytest.mark.asyncio
async def test_shopify_read_contract_and_secret_redaction() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if "shop { name }" in payload["query"]:
            return httpx.Response(200, json={"data": {"shop": {"name": "Demo"}}})
        return httpx.Response(200, json={"data": product_connection()})

    credentials = ShopifyCredentials(
        shop_domain="demo.myshopify.com", access_token=SecretStr("top-secret")
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ShopifyCommerceAdapter(credentials, client=client)
    assert "top-secret" not in repr(credentials)
    assert (await adapter.validate_connection()).healthy
    products = await adapter.list_products()
    assert products.items[0].external_id == "gid://shopify/Product/1"
    assert products.items[0].cost == 8
    inventory = await adapter.get_inventory()
    assert inventory[0].quantity == 4
    await client.aclose()


@pytest.mark.asyncio
async def test_shopify_rate_limit_retry_is_bounded() -> None:
    calls = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"})

    async def no_sleep(delay: float) -> None:
        return None

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    adapter = ShopifyCommerceAdapter(
        ShopifyCredentials(shop_domain="demo.myshopify.com", access_token=SecretStr("secret")),
        client=client,
        max_retries=2,
        sleep=no_sleep,
    )
    with pytest.raises(RateLimitError, match="exhausted"):
        await adapter.list_products()
    assert calls == 3
    await client.aclose()


def test_shopify_webhook_signature() -> None:
    import base64
    import hashlib
    import hmac

    body = b'{"id":1}'
    secret = SecretStr("webhook-secret")
    signature = base64.b64encode(
        hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).digest()
    ).decode()
    assert verify_shopify_webhook(body, signature, secret)
    assert not verify_shopify_webhook(body, "invalid", secret)
