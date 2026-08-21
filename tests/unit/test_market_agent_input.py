from datetime import UTC, datetime
from uuid import uuid4

from apps.api.routers.admin import _market_agent_input

from commerce_agent.infrastructure.db.models import (
    ProductCandidateModel,
    RawTrendObservationModel,
)


def test_market_agent_input_uses_only_identified_evidence_sources() -> None:
    now = datetime.now(UTC)
    tenant_id = uuid4()
    candidate = ProductCandidateModel(
        id=uuid4(),
        tenant_id=tenant_id,
        canonical_name="수납정리함",
        brand=None,
        category_path=["생활/건강"],
        description=None,
        attributes_json={
            "commercial_evidence": {
                "supplier_name": "검증 공급처",
                "supplier_cost": 10000,
                "expected_sale_price": 25000,
            }
        },
        primary_image_url=None,
        source_count=1,
        first_seen_at=now,
        last_seen_at=now,
        dedupe_key="market-agent-input",
        status="discovered",
        created_at=now,
        updated_at=now,
    )
    observation = RawTrendObservationModel(
        id=uuid4(),
        tenant_id=tenant_id,
        candidate_id=candidate.id,
        source="naver",
        source_id="naver-source-id",
        title_raw=candidate.canonical_name,
        url="https://datalab.naver.com",
        price=None,
        currency=None,
        observed_metrics={"latest_ratio": 42.0, "growth_7d": 0.1},
        observed_at=now,
        raw_metadata={
            "real_data": True,
            "series": [{"period": "2026-08-01", "ratio": 42.0}],
        },
        created_at=now,
        updated_at=now,
    )

    result = _market_agent_input(
        candidate,
        observation,
        {"keyword": "수납정리함", "monthly_searches": 5000},
    )

    assert [item.data["market"] for item in result.observations] == [
        "naver",
        "operator_input",
    ]
    assert set(result.candidate.source_observation_ids) == {
        f"naver-shopping-insight:{observation.id}",
        f"operator-commercial-evidence:{candidate.id}",
    }
    assert all(item.data.get("market") != "coupang" for item in result.observations)
