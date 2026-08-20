from collections import Counter
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from commerce_agent.domain.common import utc_now
from commerce_agent.domain.products.normalization import ProductNormalizer, is_near_duplicate
from commerce_agent.infrastructure.db.models import (
    ProductCandidateModel,
    RawTrendObservationModel,
)
from commerce_agent.integrations.trend_sources.base import TrendQuery, TrendSource


class TrendIngestionResult(BaseModel):
    raw_items: int
    candidates_created: int
    candidates_total: int
    observations_by_candidate: dict[str, int]


class TrendIngestionService:
    def __init__(self, session: AsyncSession, normalizer: ProductNormalizer | None = None) -> None:
        self._session = session
        self._normalizer = normalizer or ProductNormalizer()

    async def ingest(
        self, tenant_id: UUID, sources: Sequence[TrendSource], query: TrendQuery
    ) -> TrendIngestionResult:
        now = utc_now()
        candidates = list(
            (
                await self._session.scalars(
                    select(ProductCandidateModel).where(
                        ProductCandidateModel.tenant_id == tenant_id
                    )
                )
            ).all()
        )
        created = 0
        raw_count = 0
        linked_candidate_ids: list[UUID] = []
        for source in sources:
            for item in await source.discover(query):
                raw_count += 1
                normalized = self._normalizer.normalize(item.title, item.metadata)
                candidate = next(
                    (value for value in candidates if value.dedupe_key == normalized.dedupe_key),
                    None,
                )
                if candidate is None:
                    candidate = next(
                        (
                            value
                            for value in candidates
                            if value.category_path == normalized.category_id.split(".")
                            and is_near_duplicate(value.canonical_name, normalized.canonical_name)
                        ),
                        None,
                    )
                if candidate is None:
                    candidate = ProductCandidateModel(
                        tenant_id=tenant_id,
                        canonical_name=normalized.canonical_name,
                        brand=normalized.brand,
                        category_path=normalized.category_id.split("."),
                        description=None,
                        attributes_json=normalized.attributes,
                        primary_image_url=item.image_url,
                        source_count=0,
                        first_seen_at=item.observed_at,
                        last_seen_at=item.observed_at,
                        dedupe_key=normalized.dedupe_key,
                        status="discovered",
                        created_at=now,
                        updated_at=now,
                    )
                    self._session.add(candidate)
                    await self._session.flush()
                    candidates.append(candidate)
                    created += 1
                else:
                    if (
                        candidate.first_seen_at is None
                        or item.observed_at < candidate.first_seen_at
                    ):
                        candidate.first_seen_at = item.observed_at
                    if candidate.last_seen_at is None or item.observed_at > candidate.last_seen_at:
                        candidate.last_seen_at = item.observed_at
                    candidate.updated_at = now

                observation = await self._session.scalar(
                    select(RawTrendObservationModel).where(
                        RawTrendObservationModel.tenant_id == tenant_id,
                        RawTrendObservationModel.source == item.source,
                        RawTrendObservationModel.source_id == item.source_id,
                    )
                )
                if observation is None:
                    observation = RawTrendObservationModel(
                        tenant_id=tenant_id,
                        candidate_id=candidate.id,
                        source=item.source,
                        source_id=item.source_id,
                        title_raw=item.title,
                        url=item.url,
                        price=item.price,
                        currency=item.currency,
                        observed_metrics=item.observed_metrics,
                        observed_at=item.observed_at,
                        raw_metadata=item.metadata,
                        created_at=now,
                        updated_at=now,
                    )
                    self._session.add(observation)
                else:
                    observation.candidate_id = candidate.id
                    observation.observed_metrics = item.observed_metrics
                    observation.observed_at = item.observed_at
                    observation.updated_at = now
                linked_candidate_ids.append(candidate.id)

        counts = Counter(linked_candidate_ids)
        await self._session.flush()
        for candidate in candidates:
            persisted_count = await self._session.scalar(
                select(func.count())
                .select_from(RawTrendObservationModel)
                .where(
                    RawTrendObservationModel.tenant_id == tenant_id,
                    RawTrendObservationModel.candidate_id == candidate.id,
                )
            )
            candidate.source_count = persisted_count or 0
        await self._session.flush()
        return TrendIngestionResult(
            raw_items=raw_count,
            candidates_created=created,
            candidates_total=len(candidates),
            observations_by_candidate={str(key): value for key, value in counts.items()},
        )
