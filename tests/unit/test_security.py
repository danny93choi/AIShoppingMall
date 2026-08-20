from uuid import uuid4

import pytest

from commerce_agent.application.tenant_context import TenantContext
from commerce_agent.security.rbac import Permission, require_permission
from commerce_agent.security.redaction import redact_sensitive


def test_rbac_and_secret_pii_redaction() -> None:
    viewer = TenantContext(tenant_id=uuid4(), actor_id=uuid4(), roles=frozenset({"viewer"}))
    with pytest.raises(PermissionError):
        require_permission(viewer, Permission.DECIDE_RECOMMENDATION)
    redacted = redact_sensitive(
        {"access_token": "secret-value", "note": "email me at user@example.com"}
    )
    assert redacted == {"access_token": "[REDACTED]", "note": "email me at [EMAIL]"}
