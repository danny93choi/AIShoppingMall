from math import log10
from typing import Literal, Protocol

from pydantic import BaseModel


class KeywordMetrics(Protocol):
    keyword: str
    monthly_searches: int
    estimated_click_rate: float


GENERIC_KEYWORDS = {
    "공구",
    "금속",
    "냄새",
    "로션",
    "반도체",
    "빨대",
    "소품",
    "수납함",
    "스트레칭",
    "투명케이스",
}
NAVIGATION_SUFFIXES = ("사이트", "쇼핑몰", "스토어", "샵")
INFORMATION_SUFFIXES = ("뜻", "방법", "효능", "후기", "순위", "비교", "추천", "축하문구")
BROAD_SUFFIXES = ("용품", "제품", "상품")


class KeywordQualityAssessment(BaseModel):
    keyword: str
    status: Literal["eligible", "refine", "exclude"]
    quality_score: float
    reasons: list[str]


def assess_keyword(candidate: KeywordMetrics) -> KeywordQualityAssessment:
    keyword = candidate.keyword.strip()
    reasons: list[str] = []
    status: Literal["eligible", "refine", "exclude"] = "eligible"
    if keyword.endswith(NAVIGATION_SUFFIXES):
        status = "exclude"
        reasons.append("특정 쇼핑몰이나 사이트를 찾는 탐색어입니다.")
    elif keyword.endswith(INFORMATION_SUFFIXES):
        status = "refine"
        reasons.append("구매보다 정보 탐색 의도가 강한 검색어입니다.")
    elif keyword in GENERIC_KEYWORDS or keyword.endswith(BROAD_SUFFIXES):
        status = "refine"
        reasons.append("상품 범위가 넓어 구체적인 세부 상품명이 필요합니다.")
    elif len(keyword) <= 2:
        status = "refine"
        reasons.append("검색어가 짧아 하나의 판매 상품을 특정하기 어렵습니다.")

    if candidate.estimated_click_rate < 0.0035:
        status = "exclude"
        reasons.append("검색량 대비 쇼핑 클릭 신호가 낮습니다.")
    elif candidate.estimated_click_rate >= 0.015:
        reasons.append("검색량 대비 쇼핑 클릭 신호가 강합니다.")
    else:
        reasons.append("검색량 대비 쇼핑 클릭 신호가 확인됩니다.")

    specificity = min(max(len(keyword) - 2, 0) / 8, 1)
    demand = min(log10(max(candidate.monthly_searches, 1)) / 5, 1)
    click_intent = min(candidate.estimated_click_rate / 0.03, 1)
    penalty = {"eligible": 0, "refine": 25, "exclude": 60}[status]
    score = max(0.0, 45 * demand + 35 * click_intent + 20 * specificity - penalty)
    return KeywordQualityAssessment(
        keyword=keyword,
        status=status,
        quality_score=round(score, 1),
        reasons=reasons,
    )
