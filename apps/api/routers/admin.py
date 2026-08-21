import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import fmean, pstdev
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db_session
from apps.api.tenant import get_tenant_context
from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.application.workflows.discovery import DiscoveryWorkflow
from commerce_agent.config.settings import get_settings
from commerce_agent.domain.discovery.keyword_quality import (
    KeywordQualityAssessment,
    assess_keyword,
)
from commerce_agent.infrastructure.db.models import (
    AgentRunModel,
    CommerceConnectionModel,
    JobModel,
    MarketingDraftModel,
    OpportunityScoreModel,
    ProductCandidateModel,
    RawTrendObservationModel,
    RecommendationModel,
)
from commerce_agent.integrations.commerce.mock import MockCommerceAdapter
from commerce_agent.integrations.trend_sources.base import TrendQuery, TrendSource
from commerce_agent.integrations.trend_sources.naver import (
    CATEGORY_NAMES,
    NaverApiHubCredentials,
    NaverShoppingInsightSource,
)
from commerce_agent.integrations.trend_sources.naver_search_ad import (
    KeywordCandidate,
    NaverSearchAdCredentials,
    NaverSearchAdKeywordSource,
)
from commerce_agent.security.rbac import Permission, require_permission

ROOT = Path(__file__).resolve().parents[3]
router = APIRouter(tags=["admin"])

AUTO_DISCOVERY_SEEDS = {
    "50000000": "패션의류",
    "50000001": "패션잡화",
    "50000002": "화장품",
    "50000003": "생활가전",
    "50000004": "인테리어소품",
    "50000005": "육아용품",
    "50000006": "간편식",
    "50000007": "운동용품",
    "50000008": "생활용품",
    "50000009": "취미용품",
}

AUTO_DISCOVERY_SUBCATEGORIES = {
    "50000000": [
        "여성의류", "남성의류", "여성아우터", "남성아우터", "원피스", "여성상의",
        "남성상의", "여성하의", "남성하의", "청바지", "트레이닝복", "언더웨어",
        "잠옷", "아동의류", "스포츠의류",
    ],
    "50000001": [
        "여성가방", "남성가방", "여성신발", "남성신발", "운동화", "지갑",
        "벨트", "시계", "주얼리", "모자", "선글라스", "안경", "양말",
        "우산", "여행가방", "패션소품",
    ],
    "50000002": [
        "스킨케어", "클렌징", "선케어", "마스크팩", "메이크업", "립메이크업",
        "향수", "헤어케어", "헤어스타일링", "바디케어", "네일케어", "남성화장품",
        "미용기기", "미용소품",
    ],
    "50000003": [
        "생활가전",
        "주방가전",
        "계절가전",
        "컴퓨터주변기기",
        "모바일액세서리",
        "음향기기", "영상가전", "카메라", "게임기", "노트북", "태블릿",
        "스마트워치", "저장장치", "네트워크장비", "프린터",
    ],
    "50000004": [
        "침실가구", "거실가구", "주방가구", "학생가구", "사무용가구", "수납가구",
        "아웃도어가구", "침구", "커튼", "카페트", "조명", "홈데코", "인테리어소품",
        "DIY자재", "욕실인테리어",
    ],
    "50000005": [
        "유아동의류", "유아동신발", "유아식품", "분유", "기저귀", "물티슈",
        "수유용품", "이유식용품", "유모차", "카시트", "아기띠", "유아가구",
        "출산준비물", "목욕용품", "완구", "교구",
    ],
    "50000006": [
        "간편식", "건강식품", "다이어트식품", "음료", "커피", "차", "과자",
        "베이커리", "농산물", "쌀", "축산물", "수산물", "냉동식품", "반찬",
        "면류", "조미료", "유제품", "생수",
    ],
    "50000007": [
        "홈트레이닝", "헬스", "요가", "캠핑", "등산", "골프", "자전거",
        "수영", "낚시", "러닝", "테니스", "배드민턴", "축구", "농구",
        "스키", "보드", "스포츠보호용품",
    ],
    "50000008": [
        "주방용품",
        "수납정리용품",
        "청소용품",
        "욕실용품",
        "건강측정용품",
        "공구",
        "생활안전용품",
        "계절생활용품", "세탁용품", "구강용품", "위생용품", "안마용품",
        "건강관리용품", "의료용품", "원예용품", "보안용품", "생활잡화",
    ],
    "50000009": [
        "강아지용품", "고양이용품", "반려동물식품", "자동차용품", "오토바이용품",
        "문구", "사무용품", "악기", "취미공예", "수집품", "보드게임", "꽃",
        "여행용품", "숙박", "공연티켓", "e쿠폰",
    ],
}


def _trend_analysis(series: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(item["ratio"]) for item in series if item.get("ratio") is not None]
    if not values:
        return {}
    latest = values[-1]
    average = fmean(values)
    changes = [
        (current - previous) / max(abs(previous), 1.0)
        for previous, current in zip(values, values[1:], strict=False)
    ]

    def change_from(index: int) -> float:
        baseline = values[max(0, len(values) - index - 1)]
        return (latest - baseline) / max(abs(baseline), 1.0)

    volatility = pstdev(values) / max(abs(average), 1.0)
    seasonality_index = (max(values) - min(values)) / max(abs(average), 1.0)
    if seasonality_index >= 0.8:
        seasonality_strength = "높음"
    elif seasonality_index >= 0.4:
        seasonality_strength = "중간"
    else:
        seasonality_strength = "낮음"
    peak_cutoff = max(values) * 0.85
    peak_months = [
        int(str(item["period"])[5:7])
        for item in series
        if item.get("ratio") is not None and float(item["ratio"]) >= peak_cutoff
    ]
    peak_months = list(dict.fromkeys(peak_months))
    current_month = datetime.now(UTC).month
    months_until_peak = min(((month - current_month) % 12 for month in peak_months), default=12)
    if months_until_peak == 0:
        entry_timing = "성수기"
        entry_guidance = "현재 성수기입니다. 신규 소싱보다 재고·광고 운영을 우선 확인하세요."
    elif months_until_peak <= 3:
        entry_timing = "준비 적기"
        entry_guidance = (
            f"성수기까지 약 {months_until_peak}개월입니다. 공급처와 재고를 준비할 시점입니다."
        )
    elif seasonality_strength == "낮음":
        entry_timing = "상시 검토"
        entry_guidance = "계절 영향이 낮아 검색 수요와 수익성을 중심으로 판단할 수 있습니다."
    else:
        entry_timing = "관찰 구간"
        entry_guidance = "성수기까지 시간이 남았습니다. 가격과 경쟁 변화를 더 관찰하세요."
    if len(values) < 10:
        seasonality_strength = "데이터 부족"
        entry_timing = "판단 보류"
        entry_guidance = (
            f"최근 1년 중 {len(values)}개월만 데이터가 있어 계절성을 확정하기 어렵습니다."
        )
    return {
        "average_ratio": round(average, 2),
        "peak_ratio": round(max(values), 2),
        "change_4w": round(change_from(4), 4),
        "change_3m": round(change_from(3), 4),
        "change_period": round(change_from(len(values) - 1), 4),
        "volatility": round(volatility, 4),
        "positive_week_ratio": round(
            sum(change > 0 for change in changes) / max(len(changes), 1), 4
        ),
        "periods": len(values),
        "data_coverage": round(len(values) / 12, 4),
        "seasonality_index": round(seasonality_index, 4),
        "seasonality_strength": seasonality_strength,
        "peak_months": peak_months,
        "entry_timing": entry_timing,
        "entry_guidance": entry_guidance,
    }


class AdminDiscoveryRequest(BaseModel):
    source: Literal["naver"] = "naver"
    mode: Literal["auto", "direct"] = "auto"
    category_code: str = Field(default="50000008", pattern=r"^\d{8}$")
    subcategory: str | None = Field(default=None, min_length=1, max_length=50)
    keywords: list[str] = Field(default_factory=list, max_length=20)
    exclude_terms: list[str] = Field(default_factory=list, max_length=20)
    minimum_monthly_searches: int = Field(default=1000, ge=10, le=10_000_000)
    window_days: int = Field(default=365, ge=7, le=365)


class CommercialEvidenceRequest(BaseModel):
    supplier_name: str = Field(min_length=1, max_length=100)
    supplier_cost: Decimal = Field(ge=0)
    expected_sale_price: Decimal = Field(gt=0)
    shipping_per_unit: Decimal = Field(default=Decimal("0"), ge=0)
    minimum_order_quantity: int = Field(default=1, ge=1, le=1_000_000)
    competitor_price: Decimal | None = Field(default=None, gt=0)
    marketplace_fee_rate: Decimal = Field(default=Decimal("0.12"), ge=0, le=0.5)
    ad_cost_rate: Decimal = Field(default=Decimal("0.05"), ge=0, le=0.5)


def _commercial_evidence(body: CommercialEvidenceRequest) -> dict[str, Any]:
    landed_cost = body.supplier_cost + body.shipping_per_unit
    variable_rate = body.marketplace_fee_rate + body.ad_cost_rate
    fee_cost = body.expected_sale_price * variable_rate
    expected_profit = body.expected_sale_price - landed_cost - fee_cost
    expected_margin_rate = expected_profit / body.expected_sale_price
    break_even_price = landed_cost / max(Decimal("1") - variable_rate, Decimal("0.01"))
    price_risk = bool(
        body.competitor_price and body.expected_sale_price > body.competitor_price * Decimal("1.1")
    )
    if expected_margin_rate >= Decimal("0.25") and not price_risk:
        verdict = "판매 검토 가능"
    elif expected_margin_rate >= Decimal("0.15") and not price_risk:
        verdict = "마진 보완 필요"
    else:
        verdict = "판매 보류"
    return {
        **body.model_dump(mode="json"),
        "landed_cost": float(round(landed_cost, 2)),
        "fee_cost": float(round(fee_cost, 2)),
        "expected_profit": float(round(expected_profit, 2)),
        "expected_margin_rate": float(round(expected_margin_rate, 4)),
        "break_even_price": float(round(break_even_price, 2)),
        "price_risk": price_risk,
        "verdict": verdict,
        "updated_at": datetime.now(UTC).isoformat(),
    }


@router.get("/admin", include_in_schema=False)
async def admin_page() -> FileResponse:
    return FileResponse(ROOT / "apps/api/static/admin.html")


@router.get("/api/v1/admin/overview")
async def admin_overview(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.VIEW)
    tenant_id = context.tenant_id
    connections = list(
        (
            await session.scalars(
                select(CommerceConnectionModel).where(
                    CommerceConnectionModel.tenant_id == tenant_id
                )
            )
        ).all()
    )
    candidates = list(
        (
            await session.scalars(
                select(ProductCandidateModel)
                .where(ProductCandidateModel.tenant_id == tenant_id)
                .order_by(ProductCandidateModel.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    scores = list(
        (
            await session.scalars(
                select(OpportunityScoreModel).where(OpportunityScoreModel.tenant_id == tenant_id)
            )
        ).all()
    )
    score_by_id = {item.id: item for item in scores}
    candidate_name_by_id = {item.id: item.canonical_name for item in candidates}
    recommendations = list(
        (
            await session.scalars(
                select(RecommendationModel)
                .where(RecommendationModel.tenant_id == tenant_id)
                .order_by(RecommendationModel.rank)
                .limit(20)
            )
        ).all()
    )
    jobs = list(
        (
            await session.scalars(
                select(JobModel)
                .where(JobModel.tenant_id == tenant_id)
                .order_by(JobModel.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    runs = list(
        (
            await session.scalars(
                select(AgentRunModel)
                .where(AgentRunModel.tenant_id == tenant_id)
                .order_by(AgentRunModel.updated_at.desc())
                .limit(20)
            )
        ).all()
    )
    drafts = list(
        (
            await session.scalars(
                select(MarketingDraftModel).where(MarketingDraftModel.tenant_id == tenant_id)
            )
        ).all()
    )
    observations = list(
        (
            await session.scalars(
                select(RawTrendObservationModel)
                .where(RawTrendObservationModel.tenant_id == tenant_id)
                .order_by(RawTrendObservationModel.observed_at.desc())
                .limit(200)
            )
        ).all()
    )
    latest_observation_by_candidate: dict[UUID, RawTrendObservationModel] = {}
    for observation in observations:
        if observation.candidate_id is not None:
            latest_observation_by_candidate.setdefault(observation.candidate_id, observation)
    real_candidate_ids = {
        candidate_id
        for candidate_id, observation in latest_observation_by_candidate.items()
        if observation.raw_metadata.get("real_data", False)
    }
    real_recommendation_ids = {
        item.id for item in recommendations if item.candidate_id in real_candidate_ids
    }
    latest_discovery = jobs[0].summary_json if jobs else {}
    latest_keywords = set(latest_discovery.get("selected_keywords", []))
    keyword_stats = {
        item["keyword"]: item for item in latest_discovery.get("keyword_candidates", [])
    }
    quality_stats = {
        item["keyword"]: item for item in latest_discovery.get("keyword_assessments", [])
    }
    real_candidates_payload: list[dict[str, Any]] = []
    for item in candidates:
        if item.id not in real_candidate_ids or (
            latest_keywords and item.canonical_name not in latest_keywords
        ):
            continue
        observation = latest_observation_by_candidate[item.id]
        series = observation.raw_metadata.get("series", [])
        real_candidates_payload.append(
            {
                "id": item.id,
                "name": item.canonical_name,
                "category": ".".join(item.category_path),
                "status": item.status,
                "source_count": item.source_count,
                "trend": {
                    "source": observation.source,
                    "latest_ratio": observation.observed_metrics.get("latest_ratio"),
                    "growth": observation.observed_metrics.get("growth_7d"),
                    "series": series,
                    "category_name": observation.raw_metadata.get("category_name"),
                    "real_data": True,
                    "analysis": _trend_analysis(series),
                    "search_demand": keyword_stats.get(item.canonical_name),
                    "keyword_quality": quality_stats.get(item.canonical_name),
                    "commercial_evidence": item.attributes_json.get("commercial_evidence"),
                },
            }
        )
    maximum_latest = max(
        (float(item["trend"]["latest_ratio"] or 0) for item in real_candidates_payload),
        default=1.0,
    )
    maximum_searches = max(
        (
            int((item["trend"].get("search_demand") or {}).get("monthly_searches", 0))
            for item in real_candidates_payload
        ),
        default=0,
    )
    market_recommendations: list[dict[str, Any]] = []
    for candidate_payload in real_candidates_payload:
        trend = candidate_payload["trend"]
        analysis = trend["analysis"]
        monthly_searches = int((trend.get("search_demand") or {}).get("monthly_searches", 0))
        level = (
            monthly_searches / maximum_searches
            if maximum_searches
            else float(trend["latest_ratio"] or 0) / max(maximum_latest, 1.0)
        )
        growth_4w = float(analysis.get("change_3m", 0))
        period_growth = float(analysis.get("change_period", 0))
        consistency = float(analysis.get("positive_week_ratio", 0))
        stability = max(0.0, 1.0 - float(analysis.get("volatility", 0)))
        score = round(
            35 * level
            + 25 * max(0.0, min(1.0, 0.5 + growth_4w))
            + 15 * max(0.0, min(1.0, 0.5 + period_growth))
            + 15 * consistency
            + 10 * stability,
            1,
        )
        entry_timing = analysis.get("entry_timing")
        timing_score = {"준비 적기": 1.0, "상시 검토": 0.8, "성수기": 0.45}.get(entry_timing, 0.3)
        score = round(score * 0.9 + timing_score * 10, 1)
        if growth_4w > 0.1 and period_growth > 0 and entry_timing != "성수기":
            verdict = "상승 후보"
            reason = "최근 3개월과 1년 흐름이 함께 상승했습니다."
        elif entry_timing == "준비 적기":
            verdict = "성수기 준비 후보"
            reason = analysis.get("entry_guidance", "성수기 진입 전 준비 구간입니다.")
        elif level >= 0.6 and growth_4w <= 0:
            verdict = "규모 우세·하락 주의"
            reason = "현재 관심도는 높지만 최근 3개월 흐름은 하락입니다."
        elif growth_4w > 0:
            verdict = "반등 관찰"
            reason = "최근 3개월은 상승했지만 장기 흐름 확인이 더 필요합니다."
        else:
            verdict = "보류"
            reason = "최근 흐름이 하락하여 즉시 소싱하기에는 근거가 약합니다."
        commercial = trend.get("commercial_evidence")
        if commercial:
            margin_rate = float(commercial.get("expected_margin_rate", 0))
            score = round(score * 0.8 + max(0.0, min(margin_rate / 0.3, 1.0)) * 20, 1)
            verdict = str(commercial.get("verdict", "상업성 검토"))
            reason = (
                f"예상 마진 {margin_rate * 100:.1f}% · "
                f"개당 예상이익 {float(commercial.get('expected_profit', 0)):,.0f}원"
            )
            missing_evidence = ["실제 판매 성과"]
        else:
            score = round(score * 0.7, 1)
            verdict = "상업성 검증 필요"
            reason = "트렌드는 확인됐지만 공급가와 판매가가 없어 판매 추천을 확정할 수 없습니다."
            missing_evidence = ["공급가", "예상 판매가", "MOQ", "배송비", "경쟁가격"]
        market_recommendations.append(
            {
                "candidate_id": candidate_payload["id"],
                "name": candidate_payload["name"],
                "score": score,
                "verdict": verdict,
                "reason": reason,
                "metrics": analysis,
                "latest_ratio": trend["latest_ratio"],
                "search_demand": trend.get("search_demand"),
                "commercial_evidence": commercial,
                "missing_evidence": missing_evidence,
            }
        )
    market_recommendations.sort(
        key=lambda recommendation: (-recommendation["score"], recommendation["name"])
    )
    for rank, recommendation in enumerate(market_recommendations, start=1):
        recommendation["rank"] = rank
    observed_keyword_names = {item["name"] for item in real_candidates_payload}
    return {
        "connections": [
            {
                "id": item.id,
                "provider": item.provider,
                "name": item.display_name,
                "status": item.status,
                "last_sync_at": item.last_sync_at,
            }
            for item in connections
            if item.provider != "mock"
        ],
        "candidates": real_candidates_payload,
        "market_recommendations": market_recommendations,
        "ai_agent": {
            "enabled": bool(get_settings().openai_api_key),
            "status": "분석 워크플로 미연결",
        },
        "discovery_quality": {
            "subcategory": latest_discovery.get("subcategory"),
            "assessments": latest_discovery.get("keyword_assessments", []),
            "excluded": latest_discovery.get("excluded_keywords", []),
            "refinement_seeds": latest_discovery.get("refinement_seeds", []),
            "missing_trend_keywords": sorted(latest_keywords - observed_keyword_names),
        },
        "recommendations": [
            {
                "id": item.id,
                "rank": item.rank,
                "status": item.status,
                "summary": item.summary,
                "candidate_name": candidate_name_by_id.get(item.candidate_id, "Unknown"),
                "score": str(score_by_id[item.score_id].final_score)
                if item.score_id in score_by_id
                else None,
                "breakdown": score_by_id[item.score_id].components_json
                if item.score_id in score_by_id
                else {},
                "real_data": (
                    latest_observation_by_candidate[item.candidate_id].raw_metadata.get(
                        "real_data", False
                    )
                    if item.candidate_id in latest_observation_by_candidate
                    else False
                ),
            }
            for item in recommendations
            if item.candidate_id in real_candidate_ids
        ],
        "jobs": [
            {
                "id": item.id,
                "status": item.status,
                "progress": item.progress_percent,
                "step": item.current_step,
                "warnings": item.warnings_json,
                "errors": item.errors_json,
                "updated_at": item.updated_at,
            }
            for item in jobs
        ],
        "agent_runs": [
            {
                "id": item.id,
                "agent": item.agent_name,
                "status": item.status,
                "model": item.model_name,
                "cost": str(item.estimated_cost),
                "error": item.error_message,
            }
            for item in runs
        ],
        "marketing_drafts": [
            {
                "id": item.id,
                "recommendation_id": item.recommendation_id,
                "status": item.status,
                "content": item.content_json,
                "claims_to_verify": item.claims_to_verify,
                "risks": item.risks_json,
            }
            for item in drafts
            if item.recommendation_id in real_recommendation_ids
        ],
    }


@router.put("/api/v1/admin/candidates/{candidate_id}/commercial-evidence")
async def save_commercial_evidence(
    candidate_id: UUID,
    body: CommercialEvidenceRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    require_permission(context, Permission.RUN_DISCOVERY)
    candidate = await session.scalar(
        select(ProductCandidateModel).where(
            ProductCandidateModel.id == candidate_id,
            ProductCandidateModel.tenant_id == context.tenant_id,
        )
    )
    if candidate is None:
        raise HTTPException(status_code=404, detail="candidate not found")
    evidence = _commercial_evidence(body)
    candidate.attributes_json = {
        **candidate.attributes_json,
        "commercial_evidence": evidence,
    }
    candidate.updated_at = datetime.now(UTC)
    await session.flush()
    return evidence


@router.post("/api/v1/admin/discovery")
async def run_admin_discovery(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    body: AdminDiscoveryRequest | None = None,
) -> dict[str, Any]:
    require_permission(context, Permission.RUN_DISCOVERY)
    connection = await session.scalar(
        select(CommerceConnectionModel)
        .where(CommerceConnectionModel.tenant_id == context.tenant_id)
        .limit(1)
    )
    if connection is None:
        raise HTTPException(status_code=409, detail="connect a shop before discovery")
    request = body or AdminDiscoveryRequest()
    settings = get_settings()
    if request.subcategory and request.subcategory not in AUTO_DISCOVERY_SUBCATEGORIES.get(
        request.category_code, []
    ):
        raise HTTPException(
            status_code=422,
            detail="선택한 대분류에 포함되지 않는 세부 상품군입니다.",
        )
    selected_keywords = request.keywords
    keyword_candidates: list[KeywordCandidate] = []
    keyword_assessments: list[KeywordQualityAssessment] = []
    refinement_seeds: list[str] = []
    search_ad_source: NaverSearchAdKeywordSource | None = None
    if request.mode == "auto":
        if (
            settings.naver_search_ad_api_key is None
            or settings.naver_search_ad_secret_key is None
            or settings.naver_search_ad_customer_id is None
        ):
            raise HTTPException(
                status_code=503,
                detail=(
                    "자동 발굴에는 NAVER 검색광고 API 설정이 필요합니다: "
                    "NAVER_SEARCH_AD_API_KEY, NAVER_SEARCH_AD_SECRET_KEY, "
                    "NAVER_SEARCH_AD_CUSTOMER_ID"
                ),
            )
        search_ad_source = NaverSearchAdKeywordSource(
            NaverSearchAdCredentials(
                api_key=settings.naver_search_ad_api_key,
                secret_key=settings.naver_search_ad_secret_key,
                customer_id=settings.naver_search_ad_customer_id,
                base_url=settings.naver_search_ad_base_url,
            )
        )
        try:
            keyword_candidates = await search_ad_source.discover(
                request.subcategory
                or AUTO_DISCOVERY_SEEDS.get(
                    request.category_code,
                    CATEGORY_NAMES.get(request.category_code, "쇼핑"),
                ),
                minimum_monthly_searches=request.minimum_monthly_searches,
                exclude_terms=request.exclude_terms,
                limit=100,
            )
            initial_assessments = [assess_keyword(item) for item in keyword_candidates]
            initial_by_keyword = {item.keyword: item for item in keyword_candidates}
            refinement_seeds = [
                item.keyword
                for item in sorted(
                    initial_assessments,
                    key=lambda item: (
                        -initial_by_keyword[item.keyword].monthly_searches,
                        item.keyword,
                    ),
                )
                if item.status == "refine"
            ][:3]
            expanded_groups = await asyncio.gather(
                *(
                    search_ad_source.discover(
                        seed,
                        minimum_monthly_searches=request.minimum_monthly_searches,
                        exclude_terms=request.exclude_terms,
                        limit=40,
                    )
                    for seed in refinement_seeds
                ),
                return_exceptions=True,
            )
            candidates_by_keyword = {item.keyword: item for item in keyword_candidates}
            for expanded in expanded_groups:
                if isinstance(expanded, BaseException):
                    continue
                for candidate in expanded:
                    existing = candidates_by_keyword.get(candidate.keyword)
                    if existing is None or candidate.monthly_searches > existing.monthly_searches:
                        candidates_by_keyword[candidate.keyword] = candidate
            keyword_candidates = list(candidates_by_keyword.values())
        finally:
            await search_ad_source.close()
        keyword_assessments = [assess_keyword(item) for item in keyword_candidates]
        assessment_by_keyword = {item.keyword: item for item in keyword_assessments}
        eligible_candidates = sorted(
            (
                item
                for item in keyword_candidates
                if assessment_by_keyword[item.keyword].status == "eligible"
            ),
            key=lambda item: (
                -assessment_by_keyword[item.keyword].quality_score,
                -item.monthly_searches,
                item.keyword,
            ),
        )
        selected_keywords = [item.keyword for item in eligible_candidates[:20]]
        if not selected_keywords:
            raise HTTPException(
                status_code=422,
                detail="조건에 맞는 연관 키워드가 없습니다. 최소 월간 검색량을 낮춰보세요.",
            )
    elif not selected_keywords:
        raise HTTPException(status_code=422, detail="직접 비교할 키워드를 입력하세요.")
    trend_sources: list[TrendSource] = []
    naver_source: NaverShoppingInsightSource | None = None
    if settings.naver_api_hub_client_id is None or settings.naver_api_hub_client_secret is None:
        raise HTTPException(status_code=503, detail="NAVER API HUB credentials are not set")
    naver_source = NaverShoppingInsightSource(
        NaverApiHubCredentials(
            client_id=settings.naver_api_hub_client_id,
            client_secret=settings.naver_api_hub_client_secret,
            base_url=settings.naver_api_hub_base_url,
        )
    )
    trend_sources.append(naver_source)
    workflow = DiscoveryWorkflow(
        session=session,
        commerce_adapter=MockCommerceAdapter(ROOT / "fixtures/commerce/demo_shop.json"),
        trend_sources=trend_sources,
        scoring_config_path=ROOT / "assets/scoring/default/v1.json",
        supplier_fixture_path=ROOT / "fixtures/suppliers/demo_suppliers.json",
    )
    try:
        summary = await workflow.run(
            tenant_id=context.tenant_id,
            connection_id=connection.id,
            categories=[],
            idempotency_key="admin-discovery-naver",
            top_n=5,
            trend_query=TrendQuery(
                keywords=selected_keywords,
                exclude_terms=request.exclude_terms,
                category_code=request.category_code,
                window_days=request.window_days,
                max_results=20,
                time_unit="month",
            ),
        )
    finally:
        if naver_source is not None:
            await naver_source.close()
    job = await session.get(JobModel, summary.job_id)
    discovery_metadata = {
        "discovery_mode": request.mode,
        "subcategory": request.subcategory,
        "selected_keywords": selected_keywords,
        "keyword_candidates": [item.model_dump() for item in keyword_candidates],
        "keyword_assessments": [item.model_dump() for item in keyword_assessments],
        "excluded_keywords": [
            item.model_dump() for item in keyword_assessments if item.status != "eligible"
        ],
        "refinement_seeds": refinement_seeds,
    }
    if job is not None:
        job.summary_json = {**job.summary_json, **discovery_metadata}
        await session.flush()
    return {
        **summary.model_dump(mode="json"),
        **discovery_metadata,
    }
