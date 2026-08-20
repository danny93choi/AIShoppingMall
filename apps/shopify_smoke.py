import asyncio
import json
from datetime import UTC, datetime, timedelta

from commerce_agent.config.settings import get_settings
from commerce_agent.integrations.commerce.shopify import (
    ShopifyCommerceAdapter,
    ShopifyCredentials,
)


async def run() -> None:
    settings = get_settings()
    if not settings.shopify_shop_domain or settings.shopify_access_token is None:
        raise SystemExit("SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN are required")
    adapter = ShopifyCommerceAdapter(
        ShopifyCredentials(
            shop_domain=settings.shopify_shop_domain,
            access_token=settings.shopify_access_token,
            api_version=settings.shopify_api_version,
        )
    )
    try:
        now = datetime.now(UTC)
        health = await adapter.validate_connection()
        products = await adapter.list_products()
        orders = await adapter.list_orders(now - timedelta(days=30), now)
        inventory = await adapter.get_inventory()
        print(
            json.dumps(
                {
                    "healthy": health.healthy,
                    "products": len(products.items),
                    "orders": len(orders.items),
                    "inventory_items": len(inventory),
                },
                indent=2,
            )
        )
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(run())
