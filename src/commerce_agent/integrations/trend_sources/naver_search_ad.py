import base64
import hashlib
import hmac
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, SecretStr


class NaverSearchAdCredentials(BaseModel):
    api_key: SecretStr
    secret_key: SecretStr
    customer_id: str = Field(min_length=1)
    base_url: str = "https://api.searchad.naver.com"


class KeywordCandidate(BaseModel):
    keyword: str
    monthly_searches: int
    monthly_pc_searches: int
    monthly_mobile_searches: int
    competition: str
    average_pc_clicks: float
    average_mobile_clicks: float
    estimated_click_rate: float


class NaverSearchAdError(RuntimeError):
    """A credential-free Search Ad API error."""


class NaverSearchAdKeywordSource:
    path = "/keywordstool"

    def __init__(
        self,
        credentials: NaverSearchAdCredentials,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._credentials = credentials
        self._client = client or httpx.AsyncClient(timeout=30)
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def discover(
        self,
        seed: str,
        *,
        minimum_monthly_searches: int = 1000,
        exclude_terms: list[str] | None = None,
        limit: int = 100,
    ) -> list[KeywordCandidate]:
        timestamp = str(round(time.time() * 1000))
        method = "GET"
        message = f"{timestamp}.{method}.{self.path}"
        signature = base64.b64encode(
            hmac.new(
                self._credentials.secret_key.get_secret_value().encode(),
                message.encode(),
                hashlib.sha256,
            ).digest()
        ).decode()
        response = await self._client.get(
            f"{self._credentials.base_url.rstrip('/')}{self.path}",
            params={"hintKeywords": seed, "showDetail": "1"},
            headers={
                "X-Timestamp": timestamp,
                "X-API-KEY": self._credentials.api_key.get_secret_value(),
                "X-Customer": self._credentials.customer_id,
                "X-Signature": signature,
            },
        )
        if response.status_code in {401, 403}:
            raise NaverSearchAdError("NAVER Search Ad authentication was rejected")
        if response.status_code == 429:
            raise NaverSearchAdError("NAVER Search Ad request limit was exceeded")
        if response.status_code >= 400:
            raise NaverSearchAdError(f"NAVER Search Ad request failed ({response.status_code})")
        excluded = [term.casefold() for term in exclude_terms or [] if term.strip()]
        candidates: list[KeywordCandidate] = []
        for item in response.json().get("keywordList", []):
            keyword = str(item.get("relKeyword", "")).strip()
            if not keyword or any(term in keyword.casefold() for term in excluded):
                continue
            pc = _search_count(item.get("monthlyPcQcCnt"))
            mobile = _search_count(item.get("monthlyMobileQcCnt"))
            if pc + mobile < minimum_monthly_searches:
                continue
            candidates.append(
                KeywordCandidate(
                    keyword=keyword,
                    monthly_searches=pc + mobile,
                    monthly_pc_searches=pc,
                    monthly_mobile_searches=mobile,
                    competition=str(item.get("compIdx", "UNKNOWN")),
                    average_pc_clicks=float(item.get("monthlyAvePcClkCnt") or 0),
                    average_mobile_clicks=float(item.get("monthlyAveMobileClkCnt") or 0),
                    estimated_click_rate=round(
                        (
                            float(item.get("monthlyAvePcClkCnt") or 0)
                            + float(item.get("monthlyAveMobileClkCnt") or 0)
                        )
                        / max(pc + mobile, 1),
                        6,
                    ),
                )
            )
        candidates.sort(key=lambda item: (-item.monthly_searches, item.keyword))
        return candidates[:limit]


def _search_count(value: Any) -> int:
    if isinstance(value, int):
        return value
    text = str(value or "0").replace(",", "").strip()
    if text.startswith("<"):
        return max(int(text[1:]) - 1, 0)
    try:
        return int(float(text))
    except ValueError:
        return 0
