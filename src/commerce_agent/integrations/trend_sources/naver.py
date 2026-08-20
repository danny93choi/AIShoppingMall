from datetime import UTC, date, datetime, timedelta
from statistics import fmean
from typing import Any

import httpx
from pydantic import BaseModel, Field, SecretStr

from commerce_agent.integrations.trend_sources.base import RawTrendItem, TrendQuery

CATEGORY_NAMES = {
    "50000000": "패션의류",
    "50000001": "패션잡화",
    "50000002": "화장품/미용",
    "50000003": "디지털/가전",
    "50000004": "가구/인테리어",
    "50000005": "출산/육아",
    "50000006": "식품",
    "50000007": "스포츠/레저",
    "50000008": "생활/건강",
    "50000009": "여가/생활편의",
}


class NaverApiHubCredentials(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr
    base_url: str = Field(default="https://naverapihub.apigw.ntruss.com")


class NaverApiHubError(RuntimeError):
    """A safe, credential-free error returned by NAVER API HUB."""


class NaverShoppingInsightSource:
    name = "naver_shopping_insight"

    def __init__(
        self,
        credentials: NaverApiHubCredentials,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def discover(self, query: TrendQuery) -> list[RawTrendItem]:
        keywords = _clean_keywords(query.keywords)
        if not keywords:
            raise ValueError("at least one trend keyword is required")
        if query.category_code is None:
            raise ValueError("a NAVER Shopping category code is required")

        end_date = _last_complete_period(datetime.now(UTC).date(), query.time_unit)
        start_date = end_date - timedelta(days=query.window_days - 1)
        observed_at = datetime.now(UTC)
        items: list[RawTrendItem] = []
        excluded = {term.casefold() for term in query.exclude_terms}
        for batch_number, batch in enumerate(_batches(keywords, 5), start=1):
            body: dict[str, Any] = {
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "timeUnit": query.time_unit,
                "category": query.category_code,
                "keyword": [{"name": keyword, "param": [keyword]} for keyword in batch],
            }
            if query.device is not None:
                body["device"] = query.device
            if query.gender is not None:
                body["gender"] = query.gender
            if query.ages:
                body["ages"] = query.ages
            response = await self._client.post(
                f"{self._credentials.base_url.rstrip('/')}/shopping/v1/category/keywords",
                headers={
                    "X-NCP-APIGW-API-KEY-ID": self._credentials.client_id.get_secret_value(),
                    "X-NCP-APIGW-API-KEY": self._credentials.client_secret.get_secret_value(),
                    "Content-Type": "application/json",
                },
                json=body,
            )
            _raise_for_status(response)
            payload: dict[str, Any] = response.json()
            for result in payload.get("results", []):
                title = str(result.get("title", "")).strip()
                if not title or any(term in title.casefold() for term in excluded):
                    continue
                series: list[dict[str, str | float]] = []
                ratios: list[float] = []
                for point in result.get("data", []):
                    ratio = float(point["ratio"])
                    series.append({"period": str(point["period"]), "ratio": ratio})
                    ratios.append(ratio)
                latest = ratios[-1] if ratios else 0.0
                previous = ratios[-2] if len(ratios) >= 2 else latest
                growth = (latest - previous) / max(abs(previous), 1.0)
                items.append(
                    RawTrendItem(
                        source=self.name,
                        source_id=f"{query.category_code}:{title}:{end_date.isoformat()}",
                        title=title,
                        url="https://datalab.naver.com/shoppingInsight/sCategory.naver",
                        observed_metrics={
                            "growth_7d": growth,
                            "latest_ratio": latest,
                            "average_ratio": fmean(ratios) if ratios else 0.0,
                        },
                        observed_at=observed_at,
                        metadata={
                            "provider": "NAVER API HUB",
                            "category_code": query.category_code,
                            "category_name": CATEGORY_NAMES.get(query.category_code, "네이버쇼핑"),
                            "time_unit": query.time_unit,
                            "series": series,
                            "batch_number": batch_number,
                            "real_data": True,
                        },
                    )
                )
                if len(items) >= query.max_results:
                    return items
        return items


def _clean_keywords(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output[:20]


def _batches(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in {401, 403}:
        raise NaverApiHubError(
            "NAVER API HUB authentication or Shopping Insight permission was rejected"
        )
    if response.status_code == 429:
        raise NaverApiHubError("NAVER API HUB request limit was exceeded")
    if response.status_code >= 400:
        raise NaverApiHubError(f"NAVER API HUB request failed ({response.status_code})")


def _last_complete_period(today: date, time_unit: str) -> date:
    if time_unit == "date":
        return today - timedelta(days=1)
    if time_unit == "week":
        return today - timedelta(days=today.weekday() + 1)
    return today.replace(day=1) - timedelta(days=1)
