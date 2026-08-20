from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field


class TrendQuery(BaseModel):
    categories: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    category_code: str | None = Field(default=None, pattern=r"^\d{8}$")
    locale: str = "ko-KR"
    window_days: int = Field(default=30, ge=1, le=365)
    max_results: int = Field(default=100, ge=1, le=1000)
    exclude_terms: list[str] = Field(default_factory=list)
    time_unit: Literal["date", "week", "month"] = "week"
    device: Literal["pc", "mo"] | None = None
    gender: Literal["m", "f"] | None = None
    ages: list[Literal["10", "20", "30", "40", "50", "60"]] = Field(default_factory=list)


class RawTrendItem(BaseModel):
    source: str
    source_id: str
    title: str
    url: str
    observed_metrics: dict[str, float] = Field(default_factory=dict)
    price: Decimal | None = None
    currency: str | None = None
    image_url: str | None = None
    published_at: datetime | None = None
    observed_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TrendSource(Protocol):
    name: str

    async def discover(self, query: TrendQuery) -> list[RawTrendItem]: ...
