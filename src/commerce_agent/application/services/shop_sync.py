from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    CommerceConnectionModel,
    SalesAggregateModel,
    ShopIntelligenceProfileModel,
    ShopProductSnapshotModel,
)
from commerce_agent.integrations.commerce.base import CommerceAdapter


class ShopIntelligenceProfile(BaseModel):
    generated_at: datetime
    sales_window_days: int
    category_revenue_share: dict[str, float]
    category_unit_share: dict[str, float]
    asp_percentiles: dict[str, Decimal]
    top_product_attributes: dict[str, Any]
    repeat_purchase_proxy: float | None
    inventory_turnover_by_category: dict[str, float]
    seasonality_features: dict[str, float]
    data_coverage: float


class SyncResult(BaseModel):
    products_synced: int
    sales_rows_synced: int
    inventory_synced: int
    profile: ShopIntelligenceProfile


class ShopSyncService:
    def __init__(self, session: AsyncSession, adapter: CommerceAdapter) -> None:
        self._session = session
        self._adapter = adapter

    async def sync(self, tenant_id: UUID, connection_id: UUID) -> SyncResult:
        connection = await self._session.scalar(
            select(CommerceConnectionModel).where(
                CommerceConnectionModel.tenant_id == tenant_id,
                CommerceConnectionModel.id == connection_id,
            )
        )
        if connection is None:
            raise ValueError("commerce connection not found in tenant scope")

        now = utc_now()
        products = (await self._adapter.list_products()).items
        inventory = await self._adapter.get_inventory()
        inventory_by_product = {item.external_product_id: item.quantity for item in inventory}
        for product in products:
            values = {
                "tenant_id": tenant_id,
                "connection_id": connection_id,
                "external_product_id": product.external_id,
                "title": product.title,
                "category_path": product.category_path,
                "price": product.price,
                "currency": product.currency,
                "cost": product.cost,
                "inventory_quantity": inventory_by_product.get(
                    product.external_id, product.inventory_quantity
                ),
                "status": product.status,
                "snapshot_at": now,
                "created_at": now,
                "updated_at": now,
            }
            statement = insert(ShopProductSnapshotModel).values(**values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_shop_product_external",
                    set_={key: value for key, value in values.items() if key != "created_at"},
                )
            )

        start_at = now - timedelta(days=90)
        orders = (await self._adapter.list_orders(start_at, now + timedelta(days=1))).items
        product_costs = {product.external_id: product.cost or Decimal("0") for product in products}
        daily: dict[tuple[str, object], dict[str, Decimal | int]] = defaultdict(
            lambda: {
                "orders": 0,
                "units": 0,
                "gross_revenue": Decimal("0"),
                "discount_amount": Decimal("0"),
                "refund_amount": Decimal("0"),
                "estimated_cogs": Decimal("0"),
            }
        )
        for order in orders:
            for line in order.lines:
                row = daily[(line.external_product_id, order.ordered_at.date())]
                row["orders"] += 1
                row["units"] += line.quantity
                row["gross_revenue"] += line.unit_price * line.quantity
                row["discount_amount"] += line.discount_amount
                row["refund_amount"] += line.refund_amount
                row["estimated_cogs"] += (
                    product_costs.get(line.external_product_id, Decimal("0")) * line.quantity
                )

        for (external_product_id, day), row in daily.items():
            gross_margin = (
                row["gross_revenue"]
                - row["discount_amount"]
                - row["refund_amount"]
                - row["estimated_cogs"]
            )
            values = {
                **row,
                "tenant_id": tenant_id,
                "connection_id": connection_id,
                "external_product_id": external_product_id,
                "date": day,
                "gross_margin": gross_margin,
                "created_at": now,
                "updated_at": now,
            }
            statement = insert(SalesAggregateModel).values(**values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_sales_daily",
                    set_={key: value for key, value in values.items() if key != "created_at"},
                )
            )

        profile = self._build_profile(products, daily, inventory_by_product, now)
        profile_data = profile.model_dump(mode="python")
        profile_data["asp_percentiles"] = {
            key: str(value) for key, value in profile.asp_percentiles.items()
        }
        profile_values = {
            "tenant_id": tenant_id,
            "connection_id": connection_id,
            **profile_data,
            "created_at": now,
            "updated_at": now,
        }
        profile_statement = insert(ShopIntelligenceProfileModel).values(**profile_values)
        await self._session.execute(
            profile_statement.on_conflict_do_update(
                constraint="uq_shop_profile",
                set_={key: value for key, value in profile_values.items() if key != "created_at"},
            )
        )
        connection.last_sync_at = now
        await self._session.flush()
        return SyncResult(
            products_synced=len(products),
            sales_rows_synced=len(daily),
            inventory_synced=len(inventory),
            profile=profile,
        )

    @staticmethod
    def _build_profile(
        products: list[Any],
        daily: dict[tuple[str, object], dict[str, Decimal | int]],
        inventory: dict[str, int],
        now: datetime,
    ) -> ShopIntelligenceProfile:
        categories = {p.external_id: ".".join(p.category_path) for p in products}
        revenue: dict[str, Decimal] = defaultdict(Decimal)
        units: dict[str, int] = defaultdict(int)
        for (product_id, _), row in daily.items():
            category = categories.get(product_id, "uncategorized")
            revenue[category] += Decimal(row["gross_revenue"])
            units[category] += int(row["units"])
        total_revenue = sum(revenue.values(), Decimal("0"))
        total_units = sum(units.values())
        prices = sorted(p.price for p in products)
        p50 = prices[len(prices) // 2] if prices else Decimal("0")
        turnover = {
            category: count
            / max(
                sum(
                    inventory.get(p.external_id, 0)
                    for p in products
                    if categories[p.external_id] == category
                ),
                1,
            )
            for category, count in units.items()
        }
        return ShopIntelligenceProfile(
            generated_at=now.astimezone(UTC),
            sales_window_days=90,
            category_revenue_share={
                key: float(value / total_revenue) if total_revenue else 0.0
                for key, value in revenue.items()
            },
            category_unit_share={
                key: value / total_units if total_units else 0.0 for key, value in units.items()
            },
            asp_percentiles={"p50": p50},
            top_product_attributes={},
            repeat_purchase_proxy=None,
            inventory_turnover_by_category=turnover,
            seasonality_features={},
            data_coverage=1.0 if products and daily else 0.0,
        )
