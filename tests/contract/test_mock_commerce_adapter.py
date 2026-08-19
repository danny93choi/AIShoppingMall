from datetime import UTC, datetime
from pathlib import Path

import pytest

from commerce_agent.integrations.commerce.base import NotFoundError
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter

FIXTURE = Path(__file__).parents[2] / "fixtures" / "commerce" / "demo_shop.json"


async def test_mock_adapter_returns_normalized_dtos() -> None:
    adapter = MockCommerceAdapter(FIXTURE)
    health = await adapter.validate_connection()
    products = await adapter.list_products()
    orders = await adapter.list_orders(
        datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC)
    )
    inventory = await adapter.get_inventory()

    assert health.healthy
    assert [product.external_id for product in products.items] == ["p1", "p2"]
    assert len(orders.items) == 2
    assert len(inventory) == 2


async def test_mock_adapter_maps_missing_product_to_standard_error() -> None:
    with pytest.raises(NotFoundError):
        await MockCommerceAdapter(FIXTURE).get_product("missing")
