import json

import httpx
import pytest
from pydantic import SecretStr

from commerce_agent.integrations.trend_sources.base import TrendQuery
from commerce_agent.integrations.trend_sources.naver import (
    NaverApiHubCredentials,
    NaverApiHubError,
    NaverShoppingInsightSource,
)


@pytest.mark.asyncio
async def test_naver_shopping_insight_normalizes_real_series() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-NCP-APIGW-API-KEY-ID"] == "client-id"
        assert request.headers["X-NCP-APIGW-API-KEY"] == "top-secret"
        payload = json.loads(request.content)
        assert payload["timeUnit"] == "week"
        assert payload["category"] == "50000008"
        assert payload["keyword"] == [{"name": "텀블러", "param": ["텀블러"]}]
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "텀블러",
                        "keyword": ["텀블러"],
                        "data": [
                            {"period": "2026-08-03", "ratio": 40.0},
                            {"period": "2026-08-10", "ratio": 60.0},
                        ],
                    }
                ]
            },
        )

    credentials = NaverApiHubCredentials(
        client_id=SecretStr("client-id"), client_secret=SecretStr("top-secret")
    )
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = NaverShoppingInsightSource(credentials, client=client)
    items = await source.discover(
        TrendQuery(keywords=["텀블러"], category_code="50000008", window_days=84)
    )
    assert "top-secret" not in repr(credentials)
    assert len(items) == 1
    assert items[0].source == "naver_shopping_insight"
    assert items[0].observed_metrics["latest_ratio"] == 60.0
    assert items[0].observed_metrics["growth_7d"] == 0.5
    assert items[0].metadata["real_data"] is True
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_shopping_insight_rejects_auth_without_leaking_secret() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "Authentication Failed"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = NaverShoppingInsightSource(
        NaverApiHubCredentials(
            client_id=SecretStr("client-id"), client_secret=SecretStr("top-secret")
        ),
        client=client,
    )
    with pytest.raises(NaverApiHubError) as error:
        await source.discover(TrendQuery(keywords=["텀블러"], category_code="50000008"))
    assert "top-secret" not in str(error.value)
    await client.aclose()


@pytest.mark.asyncio
async def test_naver_shopping_insight_batches_twenty_keywords_five_at_a_time() -> None:
    batch_sizes: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        keywords = payload["keyword"]
        batch_sizes.append(len(keywords))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": item["name"],
                        "data": [{"period": "2026-08-10", "ratio": 50.0}],
                    }
                    for item in keywords
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = NaverShoppingInsightSource(
        NaverApiHubCredentials(client_id="client-id", client_secret="top-secret"),
        client=client,
    )
    items = await source.discover(
        TrendQuery(
            keywords=[f"상품{index}" for index in range(20)],
            category_code="50000008",
            max_results=20,
        )
    )
    await client.aclose()

    assert batch_sizes == [5, 5, 5, 5]
    assert len(items) == 20
    assert items[-1].metadata["batch_number"] == 4


@pytest.mark.asyncio
async def test_naver_shopping_insight_requests_one_year_as_monthly_periods() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["timeUnit"] == "month"
        start_year, start_month, _ = map(int, payload["startDate"].split("-"))
        end_year, end_month, _ = map(int, payload["endDate"].split("-"))
        assert (end_year - start_year) * 12 + end_month - start_month == 11
        return httpx.Response(200, json={"results": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = NaverShoppingInsightSource(
        NaverApiHubCredentials(client_id="client-id", client_secret="top-secret"),
        client=client,
    )
    await source.discover(
        TrendQuery(
            keywords=["계절상품"],
            category_code="50000008",
            window_days=365,
            time_unit="month",
        )
    )
    await client.aclose()
