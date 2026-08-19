import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from commerce_agent.integrations.commerce.base import (
    ConnectionHealth,
    CreateProductDraftCommand,
    ExternalInventoryItem,
    ExternalMutationResult,
    ExternalOrder,
    ExternalProduct,
    NotFoundError,
    Page,
    UpdateProductDraftCommand,
)


class MockCommerceAdapter:
    def __init__(self, fixture_path: Path) -> None:
        payload: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
        self._products = [ExternalProduct.model_validate(item) for item in payload["products"]]
        self._orders = [ExternalOrder.model_validate(item) for item in payload["orders"]]
        self._inventory = [
            ExternalInventoryItem.model_validate(item) for item in payload["inventory"]
        ]

    async def validate_connection(self) -> ConnectionHealth:
        return ConnectionHealth(healthy=True, provider="mock", checked_at=datetime.now(UTC))

    async def list_products(self, cursor: str | None = None) -> Page[ExternalProduct]:
        return Page(items=self._products)

    async def get_product(self, external_product_id: str) -> ExternalProduct:
        for product in self._products:
            if product.external_id == external_product_id:
                return product
        raise NotFoundError(external_product_id)

    async def list_orders(
        self, start_at: datetime, end_at: datetime, cursor: str | None = None
    ) -> Page[ExternalOrder]:
        return Page(
            items=[order for order in self._orders if start_at <= order.ordered_at < end_at]
        )

    async def get_inventory(self) -> list[ExternalInventoryItem]:
        return list(self._inventory)

    async def create_product_draft(
        self, command: CreateProductDraftCommand
    ) -> ExternalMutationResult:
        raise PermissionError("mock adapter is read-only in local/test")

    async def update_product_draft(
        self, command: UpdateProductDraftCommand
    ) -> ExternalMutationResult:
        raise PermissionError("mock adapter is read-only in local/test")
