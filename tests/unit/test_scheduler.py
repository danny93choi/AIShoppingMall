from datetime import UTC, datetime, timedelta
from uuid import uuid4

from apps.worker.scheduler import DiscoverySchedule


def test_discovery_schedule_due_logic() -> None:
    now = datetime(2026, 8, 20, tzinfo=UTC)
    assert DiscoverySchedule(tenant_id=uuid4()).is_due(now)
    assert not DiscoverySchedule(tenant_id=uuid4(), last_run_at=now - timedelta(hours=2)).is_due(
        now
    )
    assert DiscoverySchedule(tenant_id=uuid4(), last_run_at=now - timedelta(hours=25)).is_due(now)
