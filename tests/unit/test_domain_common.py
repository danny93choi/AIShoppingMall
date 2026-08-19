from datetime import datetime

import pytest

from commerce_agent.domain.entities import Tenant


def test_entity_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Tenant(name="test", created_at=datetime(2026, 1, 1))
