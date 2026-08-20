# API

Base path for business APIs will be `/api/v1`. Phase 0 exposes operational endpoints only.

## `GET /health/live`

Returns `200` while the API process is alive.

## `GET /health/ready`

Checks PostgreSQL and Redis concurrently. Returns `200` with `ready` when both are available,
otherwise `503` with per-dependency status.

## Commerce integrations

All Phase 2 endpoints require `X-Tenant-ID`, `X-Actor-ID`, and optionally `X-Roles` headers.

- `POST /api/v1/integrations/commerce`: create a mock connection
- `GET /api/v1/integrations/commerce`: list tenant-scoped connections
- `POST /api/v1/integrations/commerce/{id}/validate`: validate the adapter
- `POST /api/v1/integrations/commerce/{id}/sync`: sync products, sales, inventory, and profile

Phase 2 supports only the fixture-backed, read-only `mock` provider.

## Trend ingestion

- `POST /api/v1/trends/mock-ingest`: run both fixture-backed trend sources, persist raw
  provenance, normalize products, and merge duplicate candidates.

The default Phase 3 fixture emits 100 observations and deterministically merges them into five
canonical candidates. Repeating the request updates observations without adding candidates.
