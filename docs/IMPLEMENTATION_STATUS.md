# Implementation Status

Authoritative specification: `AI_Commerce_Agent_Implementation_Spec.md`

## Current Phase

Phase 12 — Pilot Readiness (complete)

## Phase Status

| Task | Description | Status |
|---|---|---|
| P0-01 | Repository and Python package | PASS |
| P0-02 | Ruff, mypy, pytest, pre-commit | PASS |
| P0-03 | Typed environment configuration | PASS |
| P0-04 | API, worker, PostgreSQL, Redis Compose stack | PASS |
| P0-05 | Liveness and dependency-aware readiness API | PASS |
| P0-06 | CI quality gates | PASS |

## Phase 1 Status

| Task | Description | Status |
|---|---|---|
| P1-01 | Core domain entities | PASS |
| P1-02 | Tenant-scoped repository interfaces | PASS |
| P1-03 | SQLAlchemy models and explicit mappers | PASS |
| P1-04 | Alembic initial migration | PASS |
| P1-05 | API tenant context and repository enforcement | PASS |
| P1-06 | UTC audit fields and presentation rule | PASS |

## Phase 2 Status

| Task | Description | Status |
|---|---|---|
| P2-01 | CommerceAdapter protocol and normalized DTOs/errors | PASS |
| P2-02 | Fixture-backed read-only MockCommerceAdapter | PASS |
| P2-03 | Idempotent product, sales, and inventory sync | PASS |
| P2-04 | ShopIntelligenceProfile builder and persistence | PASS |
| P2-05 | Tenant-scoped integration connect/list/validate/sync API | PASS |

## Phase 3 Status

| Task | Description | Status |
|---|---|---|
| P3-01 | TrendSource protocol and normalized raw DTO | PASS |
| P3-02 | Fixture-backed MockTrendSource A/B | PASS |
| P3-03 | Tenant-scoped raw observation persistence | PASS |
| P3-04 | Text, brand, model, and attribute normalizer | PASS |
| P3-05 | Versioned taxonomy asset | PASS |
| P3-06 | Exact key and fuzzy duplicate rules | PASS |
| P3-07 | Idempotent candidate creation and provenance linkage | PASS |

## Phase 4 Status

| Task | Description | Status |
|---|---|---|
| P4-01 | Validated feature models | PASS |
| P4-02 | Deterministic 0–100 normalizers | PASS |
| P4-03 | Landed cost and contribution-margin model | PASS |
| P4-04 | Hard-reject rule evaluator | PASS |
| P4-05 | Weighted OpportunityScoreCalculator | PASS |
| P4-06 | Versioned JSON scoring configuration | PASS |

## Phase 5 Status

| Task | Description | Status |
|---|---|---|
| P5-01 | Provider-independent LLMClient protocol | PASS |
| P5-02 | OpenAI Responses API implementation | PASS |
| P5-03 | Pydantic structured-output validation and repair | PASS |
| P5-04 | File-based versioned prompt registry with content hashes | PASS |
| P5-05 | AgentRunner | PASS |
| P5-06 | AgentRun and ToolCall persistence | PASS |
| P5-07 | Per-run cost budget guard | PASS |
| P5-08 | Deterministic FakeLLMClient | PASS |

## Phase 6 Status

| Task | Description | Status |
|---|---|---|
| P6-01 | Taxonomy-constrained CategorizerAgent | PASS |
| P6-02 | Evidence-grounded MarketAnalystAgent | PASS |
| P6-03 | Source-required SourcingAgent | PASS |
| P6-04 | Aggregate-only ShopFitAgent | PASS |
| P6-05 | Strict versioned agent input/output schemas | PASS |
| P6-06 | Per-agent tool allowlists and side-effect policy | PASS |
| P6-07 | Conservative confidence and missing-data rules | PASS |

## Phase 7 Status

| Task | Description | Status |
|---|---|---|
| P7-01 | Validated discovery workflow state and issue models | PASS |
| P7-02 | Persistent idempotent Job service with heartbeat | PASS |
| P7-03 | Shop sync through Top 5 step orchestration | PASS |
| P7-04 | Recoverable partial-failure handling | PASS |
| P7-05 | Parallel trend collection and candidate enrichment | PASS |
| P7-06 | Stable ranking and idempotent recommendation service | PASS |
| P7-07 | Persistent JSON run summary and score breakdown | PASS |
| P7-08 | Tenant discovery schedule due-state model | PASS |

## Phase 8 Status

| Task | Description | Status |
|---|---|---|
| P8-01 | Approval decision domain and pending-only transitions | PASS |
| P8-02 | Tenant-scoped approve/reject/defer API | PASS |
| P8-03 | Immutable append-only audit events | PASS |
| P8-04 | Deterministic MarketingAgent draft generator | PASS |
| P8-05 | Claims-to-verify and risk output | PASS |
| P8-06 | Configurable approval-gated draft and external mutation guard | PASS |

## Phase 9 Status

| Task | Description | Status |
|---|---|---|
| P9-01 | Shopify OAuth code exchange and secret-safe credentials | PASS |
| P9-02 | Connection validation | PASS |
| P9-03 | GraphQL product read sync | PASS |
| P9-04 | GraphQL order/sales read sync | PASS |
| P9-05 | Inventory read sync | PASS |
| P9-06 | Bounded 429/5xx retry handling | PASS |
| P9-07 | HMAC webhook signature verification | PASS |
| P9-08 | MockTransport contract suite | PASS |

## Phase 10 Status

| Task | Description | Status |
|---|---|---|
| P10-01 | Role/permission RBAC | PASS |
| P10-02 | SecretStore protocol and secret-safe development store | PASS |
| P10-03 | Correlation trace context and metrics registry | PASS |
| P10-04 | Recursive secret, email, and phone redaction | PASS |
| P10-05 | Bounded retry and dead-letter persistence | PASS |
| P10-06 | Transactional outbox persistence | PASS |
| P10-07 | Tenant/route/body-hash idempotency | PASS |
| P10-08 | Tenant-scoped rate limiter | PASS |
| P10-09 | Optional PostgreSQL RLS rollout guide | PASS |
| P10-10 | Backup/restore drill runbook | PASS |

## Phase 11 Status

| Task | Description | Status |
|---|---|---|
| P11-01 | Tenant/actor/role auth shell | PASS |
| P11-02 | Summary dashboard | PASS |
| P11-03 | Candidate list and evidence overview | PASS |
| P11-04 | Ranked recommendation queue | PASS |
| P11-05 | Approve/reject and marketing draft actions | PASS |
| P11-06 | Job and agent run diagnostics | PASS |
| P11-07 | Commerce integration status | PASS |

## Phase 12 Status

| Task | Description | Status |
|---|---|---|
| P12-01 | Tenant feature flags with safe defaults | PASS |
| P12-02 | Typed tenant onboarding | PASS |
| P12-03 | Conservative and growth scoring presets | PASS |
| P12-04 | Dead-letter support/admin endpoint | PASS |

## Phase 13: NAVER Korea Trend Integration

| Item | Status |
|---|---|
| NAVER API HUB Shopping Insight adapter | PASS |
| Secret-safe credential configuration | PASS |
| Read-only live API smoke test | PASS |
| Admin category/keyword trend controls | PASS |
| Real-data provenance and weekly trend display | PASS |

Live verification on 2026-08-20 returned five keyword series from NAVER API HUB. The admin
workflow displayed `NAVER REAL` provenance and completed with five observations. Incomplete
current-week data is excluded from week-over-week calculations.
| P12-05 | Tenant cost and pilot KPI dashboard API | PASS |
| P12-06 | Data retention policy | PASS |
| P12-07 | Terms/compliance checklist | PASS |
| P12-08 | Tenant-scoped pilot feedback capture | PASS |

## Phase 0 Verification

- Python runtime: 3.12.14 (container)
- `make bootstrap`: PASS in an isolated Python 3.12 environment
- Ruff lint and format: PASS, 29 files checked
- mypy strict mode: PASS, 18 source files checked
- pytest: PASS, 5 tests
- Docker Compose configuration/build/startup: PASS
- `GET /health/live`: PASS (`200`, `{"status":"ok"}`)
- `GET /health/ready`: PASS (`200`, PostgreSQL and Redis ready)

The host system Python is 3.9.6, so local non-container commands require installing Python 3.12+.

## Phase 1 Verification

- Migration `upgrade → downgrade → upgrade`: PASS in isolated `commerce_phase1_test` PostgreSQL DB
- Initial migration applied to local `commerce` development DB: PASS
- Tenant A cannot read Tenant B candidate by ID: PASS
- Repository tenant mismatch write guard: PASS
- Tenant Context header dependency: PASS
- UTC-aware datetime enforcement: PASS
- Ruff lint/format: PASS, 50 files
- mypy strict mode: PASS, 40 source files
- pytest: PASS, 10 tests

## Phase 2 Verification

- Mock adapter contract tests: PASS
- External network required: no
- Repeated sync duplicate protection: PASS (2 products, 2 daily sales rows)
- Expected category revenue share: PASS (`home.kitchen=0.8`, `home.bath=0.2`)
- Expected category unit share and ASP p50: PASS
- Phase 2 migration upgrade/downgrade/upgrade in isolated DB: PASS
- Live Compose connection and sync API smoke test: PASS
- Ruff lint: PASS
- mypy strict mode: PASS, 50 source files
- pytest: PASS, 13 tests

## Phase 3 Verification

- Two mock sources / 100 raw observations: PASS
- Intended canonical candidate count (`5`): PASS
- Same fixture rerun creates zero new candidates: PASS
- Each candidate links to 20 source observations: PASS
- Raw title, URL, source ID, metrics, metadata, and timestamp provenance: PASS
- Variation safety through critical attribute hash: PASS
- Phase 3 migration upgrade/downgrade/upgrade in isolated DB: PASS
- Live Compose API first run (`created=5`) and rerun (`created=0`): PASS
- Ruff lint/format: PASS, 72 files
- mypy strict mode: PASS, 60 source files
- pytest: PASS, 19 tests

## Phase 4 Verification

- Score calculation requires no LLM or network call: PASS
- Identical inputs produce identical scores: PASS
- Invalid weight total is rejected during config validation: PASS
- Decimal-based landed cost and contribution margin calculations: PASS
- Piecewise margin-score interpolation and threshold boundaries: PASS
- Hard-reject rules and multiple-reason reporting: PASS
- Ruff lint/format: PASS, 62 files formatted
- mypy strict mode: PASS, 74 source files
- pytest: PASS, 36 tests

## Phase 5 Verification

- Agent tests run without an API key or real provider: PASS
- Malformed structured output repaired with bounded retries: PASS
- Prompt name, version, and SHA-256 hash recorded: PASS
- Provider, model, token usage, estimated cost, latency, and errors recorded: PASS
- Cost budget exceed produces an explicit failure and preserves consumed usage: PASS
- AgentRun and tenant-scoped ToolCall database persistence: PASS
- Ruff lint/format: PASS
- mypy strict mode: PASS, 91 source files
- pytest: PASS, 44 tests

## Phase 6 Verification

- All four specialist outputs pass strict Pydantic schema validation: PASS
- Facts require source IDs and inferences require known fact IDs: PASS
- Unsupported-claim evaluation detects unavailable sources: PASS
- Supplier output without an available supplier source is rejected: PASS
- Categorizer output is limited to the supplied taxonomy: PASS
- Confidence is capped when facts or required data are missing: PASS
- Shop profile accepts aggregate fields only and rejects PII fields: PASS
- Per-agent tool allowlists reject unknown or unapproved mutation tools: PASS
- Ruff lint/format: PASS
- mypy strict mode: PASS, 99 source files
- pytest: PASS, 55 tests

## Phase 7 Verification

- `make demo-discovery` completes with fixture-only dependencies: PASS
- Demo tenant, shop sync, 100 observations, and 5 candidates: PASS
- Market, sourcing, and aggregate shop-fit enrichment: PASS
- Five deterministic scores and ranked recommendations persisted: PASS
- JSON output contains Top 5 and per-feature score breakdown: PASS
- One failed trend source degrades the run to partial without stopping it: PASS
- Reusing the idempotency key creates no duplicate scores or recommendations: PASS
- Job progress, heartbeat, completed steps, warnings, errors, and summary persisted: PASS
- Phase 7 migration downgrade/upgrade: PASS
- Ruff lint/format: PASS
- mypy strict mode: PASS, 106 source files
- pytest: PASS, 57 tests

## Phase 8 Verification

- Only pending recommendations can be decided: PASS
- Marketing draft is blocked before approval by default: PASS
- Draft output includes claims-to-verify and risks: PASS
- External mutation guard requires approval: PASS
- Audit events reject ORM update/delete operations: PASS
- Ruff, mypy, migration, and focused integration test: PASS

## Phase 9 Verification

- Provider credentials are SecretStr and absent from repr/log output: PASS
- Shopify GraphQL normalized product and inventory contract: PASS
- Rate-limit retry stops after configured attempts: PASS
- Webhook HMAC verification: PASS
- Read-only sandbox smoke command (`make shopify-smoke`): READY
- Real Shopify sandbox execution: PENDING external shop domain/token

## Phase 10 Verification

- Tenant isolation repository tests: PASS
- Secret and PII redaction tests: PASS
- Duplicate request returns stored response; body mismatch conflicts: PASS
- Failed operation is traceable in dead-letter storage: PASS
- Outbox events remain unpublished until a publisher handles them: PASS
- Rate limiting is tenant-scoped and bounded: PASS
- Restore drill and optional RLS documentation: PASS
- Ruff, mypy, migration, and focused tests: PASS

## Phase 11 Verification

- Admin shell renders all required operator surfaces: PASS
- Browser visual inspection at desktop viewport: PASS
- Dashboard reads tenant-scoped connections, candidates, scores, recommendations, jobs, agents, and drafts: PASS
- Discovery, approve/reject, and draft actions are wired to APIs: PASS
- Marketing draft route precedence regression fixed: PASS
- Ruff, mypy, and focused integration tests: PASS

## Phase 12 Verification

- Onboarding creates four safe-default feature flags: PASS
- External mutations and Shopify webhooks default disabled: PASS
- Scoring presets have weights summing to one: PASS
- Feedback rating validation and persistence: PASS
- Cost per run, workflow success, approval, and feedback metrics: PASS
- Tenant-scoped dead-letter support view: PASS
- Retention, compliance, and pilot operations documents: PASS
- Ruff, mypy, migration, focused test, and final full regression suite: PASS
