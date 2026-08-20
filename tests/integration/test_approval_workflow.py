from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.approvals import ApprovalDecision, ApprovalService
from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    AuditEventModel,
    OpportunityScoreModel,
    ProductCandidateModel,
    RecommendationModel,
    TenantModel,
)


async def test_approval_gates_marketing_and_writes_immutable_audit(
    db_session: AsyncSession,
) -> None:
    now = utc_now()
    tenant = TenantModel(
        name="Approval",
        status="active",
        timezone="UTC",
        currency="KRW",
        created_at=now,
        updated_at=now,
    )
    db_session.add(tenant)
    await db_session.flush()
    candidate = ProductCandidateModel(
        tenant_id=tenant.id,
        canonical_name="Demo Cup",
        brand=None,
        category_path=["home"],
        description=None,
        attributes_json={},
        primary_image_url=None,
        source_count=1,
        first_seen_at=now,
        last_seen_at=now,
        dedupe_key=f"approval-{uuid4()}",
        status="scored",
        created_at=now,
        updated_at=now,
    )
    db_session.add(candidate)
    await db_session.flush()
    score = OpportunityScoreModel(
        tenant_id=tenant.id,
        candidate_id=candidate.id,
        version=f"test-{uuid4()}",
        final_score=Decimal("80"),
        components_json={},
        weights_json={},
        features_json={},
        explanation_json={},
        created_at=now,
        updated_at=now,
    )
    db_session.add(score)
    await db_session.flush()
    recommendation = RecommendationModel(
        tenant_id=tenant.id,
        candidate_id=candidate.id,
        score_id=score.id,
        rank=1,
        recommendation_type="test",
        summary="demo",
        status="pending",
        created_at=now,
        updated_at=now,
    )
    db_session.add(recommendation)
    await db_session.flush()
    service = ApprovalService(db_session)

    with pytest.raises(PermissionError, match="approved"):
        await service.create_marketing_draft(
            tenant_id=tenant.id,
            actor_id=uuid4(),
            recommendation_id=recommendation.id,
            allow_before_approval=False,
        )
    actor_id = uuid4()
    await service.decide(
        tenant_id=tenant.id,
        actor_id=actor_id,
        decision=ApprovalDecision(recommendation_id=recommendation.id, status="approved"),
    )
    draft = await service.create_marketing_draft(
        tenant_id=tenant.id,
        actor_id=actor_id,
        recommendation_id=recommendation.id,
        allow_before_approval=False,
    )
    assert draft.claims_to_verify
    assert draft.risks_json
    with pytest.raises(ValueError, match="only pending"):
        await service.decide(
            tenant_id=tenant.id,
            actor_id=actor_id,
            decision=ApprovalDecision(recommendation_id=recommendation.id, status="rejected"),
        )
    event_count = await db_session.scalar(
        select(func.count())
        .select_from(AuditEventModel)
        .where(AuditEventModel.tenant_id == tenant.id)
    )
    assert event_count == 2
    event = await db_session.scalar(
        select(AuditEventModel).where(AuditEventModel.tenant_id == tenant.id)
    )
    assert event is not None
    event.payload_json = {"tampered": True}
    with pytest.raises(ValueError, match="immutable"):
        await db_session.flush()
