from datetime import datetime
from decimal import Decimal
from typing import Protocol

from pydantic import BaseModel, Field


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None


class ConnectionHealth(BaseModel):
    healthy: bool
    provider: str
    checked_at: datetime
    message: str | None = None


class ExternalProduct(BaseModel):
    external_id: str
    title: str
    description: str | None = None
    category_path: list[str] = Field(default_factory=list)
    price: Decimal
    currency: str
    cost: Decimal | None = None
    inventory_quantity: int | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ExternalOrderLine(BaseModel):
    external_product_id: str
    quantity: int = Field(gt=0)
    unit_price: Decimal
    discount_amount: Decimal = Decimal("0")
    refund_amount: Decimal = Decimal("0")


class ExternalOrder(BaseModel):
    external_id: str
    ordered_at: datetime
    currency: str
    lines: list[ExternalOrderLine]


class ExternalInventoryItem(BaseModel):
    external_product_id: str
    quantity: int
    observed_at: datetime


class CreateProductDraftCommand(BaseModel):
    title: str


class UpdateProductDraftCommand(BaseModel):
    external_product_id: str
    title: str | None = None


class ExternalMutationResult(BaseModel):
    external_id: str
    status: str


class CommerceAdapter(Protocol):
    async def validate_connection(self) -> ConnectionHealth: ...
    async def list_products(self, cursor: str | None = None) -> Page[ExternalProduct]: ...
    async def get_product(self, external_product_id: str) -> ExternalProduct: ...
    async def list_orders(
        self, start_at: datetime, end_at: datetime, cursor: str | None = None
    ) -> Page[ExternalOrder]: ...
    async def get_inventory(self) -> list[ExternalInventoryItem]: ...
    async def create_product_draft(
        self, command: CreateProductDraftCommand
    ) -> ExternalMutationResult: ...
    async def update_product_draft(
        self, command: UpdateProductDraftCommand
    ) -> ExternalMutationResult: ...


class CommerceAdapterError(Exception):
    """Base normalized adapter error."""


class AuthError(CommerceAdapterError):
    pass


class RateLimitError(CommerceAdapterError):
    pass


class PermissionError(CommerceAdapterError):
    pass


class NotFoundError(CommerceAdapterError):
    pass


class ExternalValidationError(CommerceAdapterError):
    pass


class TransientExternalError(CommerceAdapterError):
    pass


class PermanentExternalError(CommerceAdapterError):
    pass
