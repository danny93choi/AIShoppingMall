import asyncio
import base64
import hashlib
import hmac
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, Field, SecretStr

from commerce_agent.integrations.commerce.base import (
    AuthError,
    ConnectionHealth,
    CreateProductDraftCommand,
    ExternalInventoryItem,
    ExternalMutationResult,
    ExternalOrder,
    ExternalOrderLine,
    ExternalProduct,
    NotFoundError,
    Page,
    PermissionError,
    RateLimitError,
    TransientExternalError,
    UpdateProductDraftCommand,
)

Sleep = Callable[[float], Awaitable[None]]


class ShopifyCredentials(BaseModel):
    shop_domain: str = Field(pattern=r"^[a-zA-Z0-9-]+\.myshopify\.com$")
    access_token: SecretStr
    api_version: str = "2026-07"


class ShopifyOAuthClient:
    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def exchange_code(
        self, *, shop_domain: str, client_id: str, client_secret: SecretStr, code: str
    ) -> SecretStr:
        response = await self._client.post(
            f"https://{shop_domain}/admin/oauth/access_token",
            json={
                "client_id": client_id,
                "client_secret": client_secret.get_secret_value(),
                "code": code,
            },
        )
        if response.status_code in {401, 403}:
            raise AuthError("Shopify OAuth exchange rejected")
        response.raise_for_status()
        return SecretStr(str(response.json()["access_token"]))


class ShopifyCommerceAdapter:
    def __init__(
        self,
        credentials: ShopifyCredentials,
        *,
        client: httpx.AsyncClient | None = None,
        max_retries: int = 2,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None
        self._max_retries = max_retries
        self._sleep = sleep
        self._url = (
            f"https://{credentials.shop_domain}/admin/api/{credentials.api_version}/graphql.json"
        )

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def validate_connection(self) -> ConnectionHealth:
        data = await self._graphql("query { shop { name } }")
        return ConnectionHealth(
            healthy=bool(data.get("shop")), provider="shopify", checked_at=datetime.now(UTC)
        )

    async def list_products(self, cursor: str | None = None) -> Page[ExternalProduct]:
        query = """query Products($cursor: String) { products(first: 50, after: $cursor) {
          edges { cursor node { id title description productType status createdAt updatedAt
            variants(first: 1) { nodes { price inventoryQuantity
              inventoryItem { unitCost { amount currencyCode } } } }
          } } pageInfo { hasNextPage endCursor } } }"""
        connection = (await self._graphql(query, {"cursor": cursor}))["products"]
        items = [self._product(edge["node"]) for edge in connection["edges"]]
        next_cursor = (
            connection["pageInfo"]["endCursor"] if connection["pageInfo"]["hasNextPage"] else None
        )
        return Page(items=items, next_cursor=next_cursor)

    async def get_product(self, external_product_id: str) -> ExternalProduct:
        query = """query Product($id: ID!) { product(id: $id) {
          id title description productType status
          createdAt updatedAt variants(first: 1) { nodes { price inventoryQuantity
          inventoryItem { unitCost { amount currencyCode } } } } } }"""
        product = (await self._graphql(query, {"id": external_product_id})).get("product")
        if product is None:
            raise NotFoundError(external_product_id)
        return self._product(product)

    async def list_orders(
        self, start_at: datetime, end_at: datetime, cursor: str | None = None
    ) -> Page[ExternalOrder]:
        query = """query Orders($cursor: String, $filter: String!) {
          orders(first: 50, after: $cursor, query: $filter) {
          edges { node { id createdAt currencyCode lineItems(first: 100) { nodes { quantity
            originalUnitPriceSet { shopMoney { amount } }
            discountedTotalSet { shopMoney { amount } }
            variant { product { id } } } } } } pageInfo { hasNextPage endCursor } } }"""
        date_filter = f"created_at:>={start_at.isoformat()} created_at:<{end_at.isoformat()}"
        connection = (await self._graphql(query, {"cursor": cursor, "filter": date_filter}))[
            "orders"
        ]
        orders = []
        for edge in connection["edges"]:
            node = edge["node"]
            lines = []
            for line in node["lineItems"]["nodes"]:
                if not line.get("variant") or not line["variant"].get("product"):
                    continue
                unit_price = Decimal(line["originalUnitPriceSet"]["shopMoney"]["amount"])
                discounted = Decimal(line["discountedTotalSet"]["shopMoney"]["amount"])
                lines.append(
                    ExternalOrderLine(
                        external_product_id=line["variant"]["product"]["id"],
                        quantity=line["quantity"],
                        unit_price=unit_price,
                        discount_amount=max(
                            unit_price * line["quantity"] - discounted, Decimal("0")
                        ),
                    )
                )
            orders.append(
                ExternalOrder(
                    external_id=node["id"],
                    ordered_at=node["createdAt"],
                    currency=node["currencyCode"],
                    lines=lines,
                )
            )
        next_cursor = (
            connection["pageInfo"]["endCursor"] if connection["pageInfo"]["hasNextPage"] else None
        )
        return Page(items=orders, next_cursor=next_cursor)

    async def get_inventory(self) -> list[ExternalInventoryItem]:
        products = await self.list_products()
        now = datetime.now(UTC)
        return [
            ExternalInventoryItem(
                external_product_id=item.external_id,
                quantity=item.inventory_quantity or 0,
                observed_at=now,
            )
            for item in products.items
        ]

    async def create_product_draft(
        self, command: CreateProductDraftCommand
    ) -> ExternalMutationResult:
        raise PermissionError("Shopify adapter is read-only in the MVP")

    async def update_product_draft(
        self, command: UpdateProductDraftCommand
    ) -> ExternalMutationResult:
        raise PermissionError("Shopify adapter is read-only in the MVP")

    async def _graphql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        for attempt in range(self._max_retries + 1):
            response = await self._client.post(
                self._url,
                headers={
                    "X-Shopify-Access-Token": self._credentials.access_token.get_secret_value(),
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables or {}},
            )
            if response.status_code in {401, 403}:
                raise AuthError("Shopify credentials rejected")
            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= self._max_retries:
                    if response.status_code == 429:
                        raise RateLimitError("Shopify retry budget exhausted")
                    raise TransientExternalError("Shopify provider unavailable")
                delay = min(float(response.headers.get("Retry-After", "1")), 5.0)
                await self._sleep(delay)
                continue
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            if payload.get("errors"):
                raise TransientExternalError("Shopify GraphQL request failed")
            return dict(payload["data"])
        raise AssertionError("unreachable")

    @staticmethod
    def _product(node: dict[str, Any]) -> ExternalProduct:
        variant = node["variants"]["nodes"][0]
        unit_cost = variant.get("inventoryItem", {}).get("unitCost")
        return ExternalProduct(
            external_id=node["id"],
            title=node["title"],
            description=node.get("description"),
            category_path=[node["productType"]] if node.get("productType") else [],
            price=Decimal(variant["price"]),
            currency=unit_cost["currencyCode"] if unit_cost else "USD",
            cost=Decimal(unit_cost["amount"]) if unit_cost else None,
            inventory_quantity=variant.get("inventoryQuantity"),
            status=str(node["status"]).lower(),
            created_at=node.get("createdAt"),
            updated_at=node.get("updatedAt"),
        )


def verify_shopify_webhook(body: bytes, signature: str, secret: SecretStr) -> bool:
    digest = hmac.new(secret.get_secret_value().encode(), body, hashlib.sha256).digest()
    expected = base64.b64encode(digest).decode()
    return hmac.compare_digest(expected, signature)
