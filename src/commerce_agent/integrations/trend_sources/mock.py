import json
from pathlib import Path
from typing import Any

from commerce_agent.integrations.trend_sources.base import RawTrendItem, TrendQuery


class MockTrendSource:
    def __init__(self, name: str, fixture_path: Path) -> None:
        self.name = name
        payload: dict[str, Any] = json.loads(fixture_path.read_text(encoding="utf-8"))
        self._templates: list[dict[str, Any]] = payload["items"]
        self._repeat: int = payload.get("repeat", 1)

    async def discover(self, query: TrendQuery) -> list[RawTrendItem]:
        items: list[RawTrendItem] = []
        excluded = {term.casefold() for term in query.exclude_terms}
        for repeat_index in range(self._repeat):
            for template in self._templates:
                title = str(template["title"])
                if any(term in title.casefold() for term in excluded):
                    continue
                payload = {**template, "source": self.name}
                payload["source_id"] = f"{template['source_id']}-{repeat_index}"
                items.append(RawTrendItem.model_validate(payload))
                if len(items) >= query.max_results:
                    return items
        return items
