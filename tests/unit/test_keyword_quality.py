from commerce_agent.domain.discovery.keyword_quality import assess_keyword
from commerce_agent.integrations.trend_sources.naver_search_ad import KeywordCandidate


def candidate(
    keyword: str, *, searches: int = 10_000, click_rate: float = 0.02
) -> KeywordCandidate:
    return KeywordCandidate(
        keyword=keyword,
        monthly_searches=searches,
        monthly_pc_searches=2_000,
        monthly_mobile_searches=searches - 2_000,
        competition="중간",
        average_pc_clicks=20,
        average_mobile_clicks=180,
        estimated_click_rate=click_rate,
    )


def test_specific_product_keyword_is_eligible() -> None:
    assessment = assess_keyword(candidate("진공밀폐용기"))
    assert assessment.status == "eligible"
    assert assessment.quality_score > 50


def test_broad_and_navigation_keywords_are_not_selected() -> None:
    assert assess_keyword(candidate("공구")).status == "refine"
    assert assess_keyword(candidate("문구사이트")).status == "exclude"
    assert assess_keyword(candidate("체중계추천")).status == "refine"
    assert assess_keyword(candidate("칠순축하문구")).status == "refine"


def test_low_click_intent_is_excluded() -> None:
    assessment = assess_keyword(candidate("인바디체중계", click_rate=0.001))
    assert assessment.status == "exclude"
    assert "쇼핑 클릭 신호가 낮습니다" in " ".join(assessment.reasons)
