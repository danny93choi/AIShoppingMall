import re
from statistics import median
from typing import Any

import httpx
from pydantic import BaseModel, Field, SecretStr


class NaverShoppingCredentials(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    base_url: str = "https://openapi.naver.com"


class NaverProduct(BaseModel):
    title: str
    price: int = Field(gt=0)
    mall_name: str
    brand: str | None = None
    maker: str | None = None
    category: str
    url: str


class NaverShoppingResearchError(RuntimeError):
    pass


class NaverShoppingResearch:
    """Read-only NAVER Shopping research skill backed by the official Search API."""

    def __init__(
        self,
        credentials: NaverShoppingCredentials,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=20)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def research(self, keyword: str, *, display: int = 100) -> dict[str, Any]:
        response = await self._client.get(
            f"{self._credentials.base_url.rstrip('/')}/v1/search/shop.json",
            headers={
                "X-Naver-Client-Id": self._credentials.client_id.get_secret_value(),
                "X-Naver-Client-Secret": self._credentials.client_secret.get_secret_value(),
            },
            params={
                "query": keyword,
                "display": min(max(display, 1), 100),
                "sort": "sim",
                "exclude": "used:rental:cbshop",
            },
        )
        if response.status_code in {401, 403}:
            raise NaverShoppingResearchError(
                "NAVER 검색 API 인증 또는 쇼핑 검색 권한이 거부되었습니다."
            )
        if response.status_code == 429:
            raise NaverShoppingResearchError("NAVER 검색 API 일일 호출 한도를 초과했습니다.")
        if response.status_code >= 400:
            raise NaverShoppingResearchError(
                f"NAVER 쇼핑 검색 요청에 실패했습니다 ({response.status_code})."
            )
        payload = response.json()
        products = [
            product
            for item in payload.get("items", [])
            if (product := _parse_product(item)) is not None
        ]
        return _summarize(keyword, int(payload.get("total", 0)), products)


def _parse_product(item: Any) -> NaverProduct | None:
    if not isinstance(item, dict):
        return None
    try:
        price = int(item.get("lprice", 0))
    except (TypeError, ValueError):
        return None
    if price <= 0:
        return None
    title = re.sub(r"<[^>]+>", "", str(item.get("title", ""))).strip()
    if not title:
        return None
    categories = [str(item.get(f"category{level}", "")).strip() for level in range(1, 5)]
    return NaverProduct(
        title=title,
        price=price,
        mall_name=str(item.get("mallName", "네이버")).strip() or "네이버",
        brand=str(item.get("brand", "")).strip() or None,
        maker=str(item.get("maker", "")).strip() or None,
        category=" > ".join(value for value in categories if value),
        url=str(item.get("link", "")),
    )


def _percentile(values: list[int], fraction: float) -> int:
    index = round((len(values) - 1) * fraction)
    return values[max(0, min(index, len(values) - 1))]


def _round_price(value: float) -> int:
    return max(100, int(round(value / 100) * 100))


def _summarize(keyword: str, total: int, products: list[NaverProduct]) -> dict[str, Any]:
    prices = sorted(product.price for product in products)
    if not prices:
        return {
            "source": "naver_shopping_search",
            "keyword": keyword,
            "total_results": total,
            "sample_size": 0,
            "products": [],
        }
    q1 = _percentile(prices, 0.25)
    q3 = _percentile(prices, 0.75)
    iqr = q3 - q1
    lower = max(1, q1 - round(iqr * 1.5))
    upper = q3 + round(iqr * 1.5)
    normalized = [price for price in prices if lower <= price <= upper] or prices
    reference_price = _round_price(float(median(normalized)))
    marketplace_fee_rate = 0.12
    ad_cost_rate = 0.08
    target_margin_rate = 0.25
    shipping_allowance = 3000
    maximum_supplier_cost = _round_price(
        reference_price * (1 - marketplace_fee_rate - ad_cost_rate - target_margin_rate)
        - shipping_allowance
    )
    return {
        "source": "naver_shopping_search",
        "source_url": "https://openapi.naver.com/v1/search/shop.json",
        "keyword": keyword,
        "total_results": total,
        "sample_size": len(products),
        "normalized_sample_size": len(normalized),
        "minimum_price": min(normalized),
        "lower_quartile_price": _percentile(normalized, 0.25),
        "median_price": _round_price(float(median(normalized))),
        "upper_quartile_price": _percentile(normalized, 0.75),
        "maximum_price": max(normalized),
        "recommended_sale_price": reference_price,
        "maximum_supplier_cost": maximum_supplier_cost,
        "assumptions": {
            "marketplace_fee_rate": marketplace_fee_rate,
            "ad_cost_rate": ad_cost_rate,
            "target_margin_rate": target_margin_rate,
            "shipping_allowance": shipping_allowance,
        },
        "mall_count": len({product.mall_name for product in products}),
        "brand_count": len({product.brand for product in products if product.brand}),
        "products": [product.model_dump() for product in products[:10]],
    }
