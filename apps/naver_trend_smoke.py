import asyncio
import json

from commerce_agent.config.settings import get_settings
from commerce_agent.integrations.trend_sources.base import TrendQuery
from commerce_agent.integrations.trend_sources.naver import (
    NaverApiHubCredentials,
    NaverShoppingInsightSource,
)


async def run_smoke() -> None:
    settings = get_settings()
    if settings.naver_api_hub_client_id is None or settings.naver_api_hub_client_secret is None:
        raise RuntimeError("NAVER API HUB credentials are not configured")
    source = NaverShoppingInsightSource(
        NaverApiHubCredentials(
            client_id=settings.naver_api_hub_client_id,
            client_secret=settings.naver_api_hub_client_secret,
            base_url=settings.naver_api_hub_base_url,
        )
    )
    try:
        items = await source.discover(
            TrendQuery(
                keywords=["텀블러", "수납함", "욕실매트", "빨래건조대", "청소용품"],
                category_code="50000008",
                window_days=84,
                max_results=5,
                time_unit="week",
            )
        )
    finally:
        await source.close()
    print(
        json.dumps(
            {
                "provider": "NAVER API HUB Shopping Insight",
                "real_data": True,
                "items": [
                    {
                        "keyword": item.title,
                        "latest_ratio": item.observed_metrics.get("latest_ratio"),
                        "weekly_growth_percent": round(
                            item.observed_metrics.get("growth_7d", 0) * 100, 2
                        ),
                    }
                    for item in items
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(run_smoke())
