# Data Model

All timestamps are stored as timezone-aware UTC values. Tenant timezone conversion belongs at the
presentation boundary; repositories and domain entities operate in UTC.

Every tenant-owned table includes `tenant_id`. Repository methods require the tenant scope explicitly,
and candidate reads filter by both `tenant_id` and resource ID. Composite foreign keys are used where
cross-tenant references would otherwise be possible.

The domain dataclasses are independent from SQLAlchemy models. Explicit mappers translate between the
two representations.

Core Phase 1 tables: tenants, commerce_connections, product_candidates,
product_source_observations, supplier_candidates, opportunity_scores, recommendations, approvals,
jobs, and agent_runs.
