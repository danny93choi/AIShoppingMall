import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.application.services.jobs import JobService
from commerce_agent.application.services.shop_sync import ShopSyncService
from commerce_agent.application.services.trend_ingestion import TrendIngestionService
from commerce_agent.application.workflows.state import (
    DiscoveryRunSummary,
    DiscoveryWorkflowState,
    WorkflowIssue,
)
from commerce_agent.domain.common import utc_now
from commerce_agent.domain.scoring.calculator import FeatureScores, OpportunityScoreCalculator
from commerce_agent.domain.scoring.config import load_scoring_config
from commerce_agent.domain.scoring.rejections import HardRejectInput, evaluate_hard_reject
from commerce_agent.infrastructure.db.models import (
    OpportunityScoreModel,
    ProductCandidateModel,
    RawTrendObservationModel,
    RecommendationModel,
)
from commerce_agent.integrations.commerce.base import CommerceAdapter
from commerce_agent.integrations.trend_sources.base import RawTrendItem, TrendQuery, TrendSource


class CandidateEvaluation(BaseModel):
    candidate_id: UUID
    candidate_name: str
    feature_scores: FeatureScores
    enrichment: dict[str, Any]
    rejected: bool
    rejection_reasons: list[str]


class _CollectedTrendSource:
    def __init__(self, name: str, items: list[RawTrendItem]) -> None:
        self.name = name
        self._items = items

    async def discover(self, query: TrendQuery) -> list[RawTrendItem]:
        return self._items[: query.max_results]


class DiscoveryWorkflow:
    def __init__(
        self,
        *,
        session: AsyncSession,
        commerce_adapter: CommerceAdapter,
        trend_sources: list[TrendSource],
        scoring_config_path: Path,
        supplier_fixture_path: Path,
    ) -> None:
        self._session = session
        self._commerce_adapter = commerce_adapter
        self._trend_sources = trend_sources
        self._scoring_config = load_scoring_config(scoring_config_path)
        supplier_payload: dict[str, Any] = json.loads(
            supplier_fixture_path.read_text(encoding="utf-8")
        )
        self._suppliers = {str(item["brand"]): item for item in supplier_payload["suppliers"]}
        self._jobs = JobService(session)

    async def run(
        self,
        *,
        tenant_id: UUID,
        connection_id: UUID,
        categories: list[str],
        idempotency_key: str,
        max_candidates: int = 50,
        top_n: int = 5,
    ) -> DiscoveryRunSummary:
        correlation_id = uuid4()
        job = await self._jobs.create_or_restart(
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
        )
        state = DiscoveryWorkflowState(
            tenant_id=tenant_id,
            job_id=job.id,
            correlation_id=correlation_id,
            categories=categories,
            status="running",
        )
        await self._checkpoint(state, "shop_sync", 5)
        await ShopSyncService(self._session, self._commerce_adapter).sync(tenant_id, connection_id)
        state.completed_steps.append("shop_sync")

        await self._checkpoint(state, "trend_sources", 15)
        collected = await self._collect_sources(state, categories, max_candidates)
        if not collected:
            return await self._fail(
                state, "trend_sources", "NO_TREND_SOURCES", "all sources failed"
            )
        ingestion = await TrendIngestionService(self._session).ingest(
            tenant_id,
            collected,
            TrendQuery(categories=categories, max_results=max_candidates),
        )
        state.completed_steps.extend(["trend_sources", "candidate_normalization"])
        observations = list(
            (
                await self._session.scalars(
                    select(RawTrendObservationModel).where(
                        RawTrendObservationModel.tenant_id == tenant_id
                    )
                )
            ).all()
        )
        state.raw_item_ids = [f"{item.source}:{item.source_id}" for item in observations]
        candidates = list(
            (
                await self._session.scalars(
                    select(ProductCandidateModel)
                    .where(ProductCandidateModel.tenant_id == tenant_id)
                    .order_by(ProductCandidateModel.canonical_name)
                    .limit(max_candidates)
                )
            ).all()
        )
        state.candidate_ids = [candidate.id for candidate in candidates]

        await self._checkpoint(state, "parallel_enrichment", 45)
        observations_by_candidate: dict[UUID, list[RawTrendObservationModel]] = {}
        for observation in observations:
            if observation.candidate_id is not None:
                observations_by_candidate.setdefault(observation.candidate_id, []).append(
                    observation
                )
        results = await asyncio.gather(
            *(
                self._enrich_candidate(candidate, observations_by_candidate.get(candidate.id, []))
                for candidate in candidates
            ),
            return_exceptions=True,
        )
        evaluations: list[CandidateEvaluation] = []
        for candidate, result in zip(candidates, results, strict=True):
            if isinstance(result, BaseException):
                state.errors.append(
                    WorkflowIssue(
                        step="parallel_enrichment",
                        code=type(result).__name__,
                        message=str(result),
                        recoverable=True,
                        context={"candidate_id": str(candidate.id)},
                    )
                )
            else:
                evaluations.append(result)
                state.analyzed_ids.append(candidate.id)
        state.completed_steps.append("parallel_enrichment")

        await self._checkpoint(state, "scoring", 70)
        ranked = await self._persist_scores(state, evaluations)
        state.completed_steps.append("scoring")
        recommendations = await self._persist_recommendations(state, ranked[:top_n])
        state.completed_steps.extend(["ranking", "recommendations"])
        state.status = "partial" if state.errors or state.warnings else "succeeded"
        summary = DiscoveryRunSummary(
            job_id=state.job_id,
            correlation_id=state.correlation_id,
            status=state.status,
            raw_items=ingestion.raw_items,
            candidates=len(state.candidate_ids),
            analyzed=len(state.analyzed_ids),
            scored=len(state.scored_ids),
            recommendations=len(state.recommendation_ids),
            warning_count=len(state.warnings),
            error_count=len(state.errors),
            top_recommendations=recommendations,
        )
        await self._jobs.update(
            state, step=None, progress=100, summary=summary.model_dump(mode="json")
        )
        return summary

    async def _collect_sources(
        self, state: DiscoveryWorkflowState, categories: list[str], max_results: int
    ) -> list[TrendSource]:
        query = TrendQuery(categories=categories, max_results=max_results)
        discovered = await asyncio.gather(
            *(source.discover(query) for source in self._trend_sources), return_exceptions=True
        )
        collected: list[TrendSource] = []
        for source, result in zip(self._trend_sources, discovered, strict=True):
            if isinstance(result, BaseException):
                state.warnings.append(
                    WorkflowIssue(
                        step="trend_sources",
                        code=type(result).__name__,
                        message=str(result),
                        recoverable=True,
                        context={"source": source.name},
                    )
                )
            else:
                collected.append(_CollectedTrendSource(source.name, result))
        return collected

    async def _enrich_candidate(
        self, candidate: ProductCandidateModel, observations: list[RawTrendObservationModel]
    ) -> CandidateEvaluation:
        await asyncio.sleep(0)
        growth_values = [
            Decimal(str(item.observed_metrics.get("growth_7d", 0))) for item in observations
        ]
        growth = sum(growth_values, Decimal("0")) / max(len(growth_values), 1)
        source_names = {item.source for item in observations}
        trend = _bounded(growth * 200)
        demand = _bounded(Decimal("45") + growth * 100)
        competition = _bounded(Decimal("75") - growth * 30)
        category = ".".join(candidate.category_path)
        shop_fit = Decimal("82") if category.startswith("home") else Decimal("60")
        confidence = Decimal("90") if len(source_names) >= 2 else Decimal("60")
        supplier = self._suppliers.get(candidate.brand or "")
        scores = FeatureScores(
            trend=trend,
            demand=demand,
            competition=competition,
            margin=Decimal("75"),
            supply=Decimal("80") if supplier else Decimal("0"),
            shop_fit=shop_fit,
            confidence=confidence,
        )
        rejection = evaluate_hard_reject(
            HardRejectInput(
                margin_rate=Decimal("0.25"),
                confidence_score=confidence,
                supplier_count=1 if supplier else 0,
                category_id=category,
                expected_selling_price=Decimal("25000"),
                market_reference_price=Decimal("25000"),
            ),
            self._scoring_config.hard_reject,
        )
        return CandidateEvaluation(
            candidate_id=candidate.id,
            candidate_name=candidate.canonical_name,
            feature_scores=scores,
            enrichment={
                "market": {"growth_7d": str(growth), "source_count": len(source_names)},
                "sourcing": {
                    "supplier_source_ids": [str(supplier["source_id"])] if supplier else [],
                    "supplier_name": supplier["supplier_name"] if supplier else None,
                    "verified": False,
                },
                "shop_fit": {"category": category, "aggregate_only": True},
            },
            rejected=rejection.rejected,
            rejection_reasons=rejection.reason_codes,
        )

    async def _persist_scores(
        self, state: DiscoveryWorkflowState, evaluations: list[CandidateEvaluation]
    ) -> list[tuple[CandidateEvaluation, OpportunityScoreModel]]:
        calculated: list[tuple[CandidateEvaluation, Decimal]] = []
        calculator = OpportunityScoreCalculator()
        for evaluation in evaluations:
            if evaluation.rejected:
                continue
            score = calculator.calculate(
                evaluation.candidate_id, evaluation.feature_scores, self._scoring_config
            )
            values = {
                "tenant_id": state.tenant_id,
                "candidate_id": evaluation.candidate_id,
                "version": score.version,
                "final_score": score.final_score,
                "components_json": {
                    key: str(value) for key, value in score.scores.model_dump().items()
                },
                "weights_json": {key: str(value) for key, value in score.weights.items()},
                "features_json": evaluation.enrichment,
                "explanation_json": {"hard_reject_reasons": evaluation.rejection_reasons},
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }
            statement = insert(OpportunityScoreModel).values(**values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_score_candidate_version",
                    set_={key: value for key, value in values.items() if key != "created_at"},
                )
            )
            calculated.append((evaluation, score.final_score))
        await self._session.flush()
        score_models = list(
            (
                await self._session.scalars(
                    select(OpportunityScoreModel).where(
                        OpportunityScoreModel.tenant_id == state.tenant_id,
                        OpportunityScoreModel.version == self._scoring_config.version,
                    )
                )
            ).all()
        )
        by_candidate = {score.candidate_id: score for score in score_models}
        ranked = [
            (evaluation, by_candidate[evaluation.candidate_id]) for evaluation, _ in calculated
        ]
        ranked.sort(key=lambda item: (-item[1].final_score, item[0].candidate_name))
        state.scored_ids = [item[1].id for item in ranked]
        return ranked

    async def _persist_recommendations(
        self,
        state: DiscoveryWorkflowState,
        ranked: list[tuple[CandidateEvaluation, OpportunityScoreModel]],
    ) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        for rank, (evaluation, score) in enumerate(ranked, start=1):
            now = utc_now()
            values = {
                "tenant_id": state.tenant_id,
                "candidate_id": evaluation.candidate_id,
                "score_id": score.id,
                "rank": rank,
                "recommendation_type": "test",
                "summary": f"{evaluation.candidate_name}: opportunity score {score.final_score}",
                "status": "pending",
                "created_at": now,
                "updated_at": now,
            }
            statement = insert(RecommendationModel).values(**values)
            await self._session.execute(
                statement.on_conflict_do_update(
                    constraint="uq_recommendation_score",
                    set_={key: value for key, value in values.items() if key != "created_at"},
                )
            )
            output.append(
                {
                    "rank": rank,
                    "candidate_id": str(evaluation.candidate_id),
                    "name": evaluation.candidate_name,
                    "score": str(score.final_score),
                    "score_breakdown": score.components_json,
                }
            )
        await self._session.flush()
        recommendation_models = list(
            (
                await self._session.scalars(
                    select(RecommendationModel).where(
                        RecommendationModel.tenant_id == state.tenant_id,
                        RecommendationModel.score_id.in_([score.id for _, score in ranked]),
                    )
                )
            ).all()
        )
        state.recommendation_ids = [item.id for item in recommendation_models]
        return output

    async def _checkpoint(self, state: DiscoveryWorkflowState, step: str, progress: int) -> None:
        await self._jobs.update(state, step=step, progress=progress)

    async def _fail(
        self, state: DiscoveryWorkflowState, step: str, code: str, message: str
    ) -> DiscoveryRunSummary:
        state.status = "failed"
        state.errors.append(WorkflowIssue(step=step, code=code, message=message, recoverable=False))
        summary = DiscoveryRunSummary(
            job_id=state.job_id,
            correlation_id=state.correlation_id,
            status=state.status,
            raw_items=0,
            candidates=0,
            analyzed=0,
            scored=0,
            recommendations=0,
            warning_count=len(state.warnings),
            error_count=len(state.errors),
            top_recommendations=[],
        )
        await self._jobs.update(
            state, step=step, progress=100, summary=summary.model_dump(mode="json")
        )
        return summary


def _bounded(value: Decimal) -> Decimal:
    return min(max(value, Decimal("0")), Decimal("100")).quantize(Decimal("0.001"))
