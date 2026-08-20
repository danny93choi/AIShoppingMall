import httpx

from commerce_agent.integrations.trend_sources.naver_search_ad import (
    NaverSearchAdCredentials,
    NaverSearchAdKeywordSource,
)


async def test_search_ad_discovers_and_ranks_real_keyword_candidates() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/keywordstool"
        assert request.url.params["hintKeywords"] == "생활용품"
        assert request.headers["X-API-KEY"] == "api-key"
        assert request.headers["X-Customer"] == "customer"
        assert request.headers["X-Signature"]
        return httpx.Response(
            200,
            json={
                "keywordList": [
                    {
                        "relKeyword": "수납함",
                        "monthlyPcQcCnt": 1200,
                        "monthlyMobileQcCnt": 8800,
                        "compIdx": "HIGH",
                        "monthlyAvePcClkCnt": 12.3,
                        "monthlyAveMobileClkCnt": 91.2,
                    },
                    {
                        "relKeyword": "대형수납함",
                        "monthlyPcQcCnt": 500,
                        "monthlyMobileQcCnt": 2500,
                        "compIdx": "MEDIUM",
                    },
                    {
                        "relKeyword": "낮은검색어",
                        "monthlyPcQcCnt": "< 10",
                        "monthlyMobileQcCnt": 30,
                        "compIdx": "LOW",
                    },
                ]
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    source = NaverSearchAdKeywordSource(
        NaverSearchAdCredentials(
            api_key="api-key",
            secret_key="secret-key",
            customer_id="customer",
        ),
        client=client,
    )
    results = await source.discover(
        "생활용품", minimum_monthly_searches=1000, exclude_terms=["대형"]
    )
    await client.aclose()

    assert [item.keyword for item in results] == ["수납함"]
    assert results[0].monthly_searches == 10_000
    assert results[0].competition == "HIGH"
    assert results[0].estimated_click_rate == 0.01035
