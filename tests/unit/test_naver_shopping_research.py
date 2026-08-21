import httpx
from pydantic import SecretStr

from commerce_agent.integrations.market_research.naver_shopping import (
    NaverShoppingCredentials,
    NaverShoppingResearch,
)


async def test_naver_shopping_research_builds_price_and_cost_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Naver-Client-Id"] == "client"
        assert request.url.params["display"] == "100"
        assert request.url.params["exclude"] == "used:rental:cbshop"
        prices = [10000, 12000, 14000, 16000, 18000, 20000, 1000000]
        return httpx.Response(
            200,
            json={
                "total": 321,
                "items": [
                    {
                        "title": f"<b>텀블러</b> {index}",
                        "lprice": str(price),
                        "mallName": f"판매처 {index % 3}",
                        "brand": f"브랜드 {index % 2}",
                        "category1": "생활/건강",
                        "category2": "주방용품",
                        "link": f"https://example.com/{index}",
                    }
                    for index, price in enumerate(prices)
                ],
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    skill = NaverShoppingResearch(
        NaverShoppingCredentials(client_id=SecretStr("client"), client_secret=SecretStr("secret")),
        client=client,
    )
    result = await skill.research("텀블러")

    assert result["total_results"] == 321
    assert result["sample_size"] == 7
    assert result["normalized_sample_size"] == 6
    assert result["median_price"] == 15000
    assert result["recommended_sale_price"] == 15000
    assert result["maximum_supplier_cost"] == 5200
    assert result["mall_count"] == 3
    assert result["products"][0]["title"] == "텀블러 0"
    await client.aclose()
