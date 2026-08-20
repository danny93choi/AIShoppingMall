from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.infrastructure.db.models import (
    ApprovalModel,
    AuditEventModel,
    MarketingDraftModel,
    ProductCandidateModel,
    RecommendationModel,
)

Decision = Literal["approved", "rejected", "deferred"]


class ApprovalDecision(BaseModel):
    recommendation_id: UUID
    status: Decision
    note: str | None = None


class MarketingDraftContent(BaseModel):
    positioning: str
    target_segments: list[str]
    offer: dict[str, Any]
    channels: dict[str, Any]
    claims_to_verify: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class ApprovalService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def decide(
        self, *, tenant_id: UUID, actor_id: UUID, decision: ApprovalDecision
    ) -> RecommendationModel:
        recommendation = await self._session.scalar(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id,
                RecommendationModel.id == decision.recommendation_id,
            )
        )
        if recommendation is None:
            raise ValueError("recommendation not found in tenant scope")
        if recommendation.status != "pending":
            raise ValueError("only pending recommendations can be decided")
        now = utc_now()
        action = decision.status.removesuffix("d")
        approval = ApprovalModel(
            tenant_id=tenant_id,
            resource_type="recommendation",
            resource_id=recommendation.id,
            action=action,
            requested_by=actor_id,
            status=decision.status,
            decided_by=actor_id,
            decided_at=now,
            decision_note=decision.note,
            created_at=now,
            updated_at=now,
        )
        event = AuditEventModel(
            tenant_id=tenant_id,
            event_type=f"recommendation.{decision.status}",
            resource_type="recommendation",
            resource_id=recommendation.id,
            actor_id=actor_id,
            payload_json={"status": decision.status, "note": decision.note},
            created_at=now,
            updated_at=now,
        )
        recommendation.status = decision.status
        recommendation.updated_at = now
        self._session.add_all([approval, event])
        await self._session.flush()
        return recommendation

    async def create_marketing_draft(
        self,
        *,
        tenant_id: UUID,
        actor_id: UUID,
        recommendation_id: UUID,
        allow_before_approval: bool,
    ) -> MarketingDraftModel:
        recommendation = await self._session.scalar(
            select(RecommendationModel).where(
                RecommendationModel.tenant_id == tenant_id,
                RecommendationModel.id == recommendation_id,
            )
        )
        if recommendation is None:
            raise ValueError("recommendation not found in tenant scope")
        if recommendation.status != "approved" and not allow_before_approval:
            raise PermissionError("marketing draft requires an approved recommendation")
        existing = await self._session.scalar(
            select(MarketingDraftModel).where(
                MarketingDraftModel.tenant_id == tenant_id,
                MarketingDraftModel.recommendation_id == recommendation_id,
            )
        )
        if existing is not None:
            return existing
        candidate = await self._session.scalar(
            select(ProductCandidateModel).where(
                ProductCandidateModel.tenant_id == tenant_id,
                ProductCandidateModel.id == recommendation.candidate_id,
            )
        )
        if candidate is None:
            raise ValueError("candidate not found in tenant scope")
        content = self._draft_for(candidate.canonical_name)
        now = utc_now()
        draft = MarketingDraftModel(
            id=uuid4(),
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            schema_version="1.0",
            content_json=content.model_dump(mode="json", exclude={"claims_to_verify", "risks"}),
            claims_to_verify=content.claims_to_verify,
            risks_json=content.risks,
            status="draft",
            created_at=now,
            updated_at=now,
        )
        event = AuditEventModel(
            tenant_id=tenant_id,
            event_type="marketing.draft.created",
            resource_type="marketing_draft",
            resource_id=draft.id,
            actor_id=actor_id,
            payload_json={"recommendation_id": str(recommendation_id)},
            created_at=now,
            updated_at=now,
        )
        self._session.add_all([draft, event])
        await self._session.flush()
        return draft

    @staticmethod
    def require_external_mutation_approval(recommendation_status: str) -> None:
        if recommendation_status != "approved":
            raise PermissionError("external mutation requires an approved recommendation")

    @staticmethod
    def _draft_for(product_name: str) -> MarketingDraftContent:
        return MarketingDraftContent(
            positioning=f"일상에 자연스럽게 더하는 {product_name}",
            target_segments=["기존 쇼핑몰 관심 고객"],
            offer={"type": "test_launch", "discount_claim": None},
            channels={
                "instagram": {"copies": [f"새로운 {product_name}을 확인해 보세요."]},
                "email": {"subject_lines": [f"{product_name} 테스트 출시"], "body_outline": []},
                "product_page": {"headline": product_name, "bullets": []},
            },
            claims_to_verify=["제품 상세 사양", "재고 및 배송 일정"],
            risks=["검증되지 않은 효능·최상급 표현 사용 금지"],
        )
