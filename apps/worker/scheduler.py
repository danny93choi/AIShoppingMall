from datetime import UTC, datetime, timedelta
from uuid import UUID

from pydantic import BaseModel, Field


class DiscoverySchedule(BaseModel):
    tenant_id: UUID
    interval_hours: int = Field(default=24, ge=1, le=168)
    enabled: bool = True
    last_run_at: datetime | None = None

    def is_due(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if not self.enabled:
            return False
        return self.last_run_at is None or current >= self.last_run_at + timedelta(
            hours=self.interval_hours
        )
