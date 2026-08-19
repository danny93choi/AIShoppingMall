# ADR-0003: Explicit Tenant Scoping

- Status: Accepted
- Date: 2026-08-19

## Context

Tenant data leakage is a P0 defect. Relying on callers to remember an optional filter is insufficient.

## Decision

Every tenant-owned table stores and indexes `tenant_id`. Repository contracts require tenant scope on
every operation, reads filter by tenant and resource ID, and writes reject entities whose tenant does
not match the requested scope. Composite tenant-aware constraints protect cross-tenant references.
PostgreSQL RLS remains an optional Phase 10 defense-in-depth measure.

## Consequences

Repository APIs are slightly more verbose. Tenant isolation is explicit, testable, and independent of
the web framework or database session lifecycle.
