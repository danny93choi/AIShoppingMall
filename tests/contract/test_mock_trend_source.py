from pathlib import Path

from commerce_agent.integrations.trend_sources.base import TrendQuery
from commerce_agent.integrations.trend_sources.mock import MockTrendSource

FIXTURE = Path(__file__).parents[2] / "fixtures" / "trend_sources" / "mock_trend_a.json"


async def test_mock_trend_source_returns_50_valid_items() -> None:
    source = MockTrendSource("mock_trend_a", FIXTURE)
    items = await source.discover(TrendQuery(max_results=100))
    assert len(items) == 50
    assert len({item.source_id for item in items}) == 50
    assert all(item.source == "mock_trend_a" for item in items)


async def test_mock_trend_source_honors_limit_and_exclusions() -> None:
    source = MockTrendSource("mock_trend_a", FIXTURE)
    items = await source.discover(TrendQuery(max_results=3, exclude_terms=["타월"]))
    assert len(items) == 3
    assert all("타월" not in item.title for item in items)
