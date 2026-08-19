# AI Commerce Agent Platform — Codex 구현 설계서

**문서 버전:** 1.0  
**대상:** Codex 및 백엔드/AI/프론트엔드 엔지니어  
**목표:** 트렌디한 상품의 AI 발굴·카테고리화·시장성 평가·소싱·쇼핑몰 적합도 분석·마케팅 제안까지 수행하는 멀티테넌트 AI Commerce Agent SaaS를 단계적으로 구현한다.  
**구현 원칙:** 특정 쇼핑몰·특정 LLM·특정 에이전트 런타임에 핵심 로직을 종속시키지 않는다.

---

## 0. Codex에게 주는 실행 계약

이 문서는 단순 참고자료가 아니라 구현 순서와 완료 기준을 포함한 **실행 명세**다. Codex는 다음 규칙을 지킨다.

1. **Phase를 건너뛰지 않는다.** 각 Phase의 Acceptance Criteria를 모두 통과한 뒤 다음 Phase로 진행한다.
2. 모든 기능은 먼저 인터페이스와 도메인 모델을 정의하고, 그 다음 구현한다.
3. Agent가 외부 API나 DB에 직접 접근하지 않는다. 반드시 Tool/Service Interface를 통해 접근한다.
4. LLM 출력은 가능한 한 자유 텍스트가 아니라 Pydantic 기반 Structured Output으로 받는다.
5. 계산 가능한 값(마진율, 점수 합산, 재고 수량, 가격 비교 등)은 LLM이 아니라 deterministic code로 계산한다.
6. 외부 시스템 변경(create/update/delete/send/publish)은 기본적으로 **Human Approval** 이후에만 수행한다.
7. 모든 비동기 작업은 `job_id`, `tenant_id`, `correlation_id`, `idempotency_key`를 갖는다.
8. 모든 Agent 실행은 재현 가능하도록 input, tool calls, model, prompt version, output, latency, token usage, cost, error를 기록한다.
9. 멀티테넌트 데이터는 모든 테이블에서 `tenant_id`로 격리한다. tenant 간 데이터 누출은 P0 버그다.
10. 새 통합은 `Adapter`를 추가하는 방식으로 확장하며 Core Domain을 수정하지 않는 것을 우선한다.
11. 구현 중 설계 변경이 필요하면 `docs/adr/ADR-XXXX-*.md`에 이유·대안·결론을 남긴다.
12. 각 Phase 완료 시 `docs/IMPLEMENTATION_STATUS.md`를 갱신한다.
13. 테스트 없는 기능은 완료로 간주하지 않는다.
14. 샘플/개발 환경에서는 실제 결제·광고 집행·상품 공개와 같은 irreversible side effect를 실행하지 않는다.

---

# 1. 제품 정의

## 1.1 한 문장 정의

**판매자의 쇼핑몰 데이터와 외부 시장 트렌드를 결합해 “다음에 무엇을 팔아야 하는지”를 찾고, 소싱 가능성과 수익성을 검증하며, 승인된 상품에 대해 마케팅 실행안까지 생성하는 AI MD/Commerce Agent 플랫폼.**

## 1.2 핵심 가치

기존 쇼핑몰 AI는 대체로 “이미 보유한 상품을 누구에게 어떻게 팔 것인가”에 집중한다. 본 제품의 핵심은 그 앞단이다.

- 시장에서 무엇이 뜨는가?
- 어떤 상품군이 성장하는가?
- 이 상품이 **우리 쇼핑몰 고객에게도** 맞는가?
- 공급 가능한가? 가격·MOQ·배송 조건은 어떤가?
- 실제로 팔았을 때 기여이익이 남는가?
- 어떤 포지셔닝과 마케팅 방식이 적합한가?

## 1.3 1차 타깃 고객

MVP 기준:

- 카페24/Shopify/자사몰을 운영하는 중소형 D2C 사업자
- 신규 SKU 발굴과 소싱을 수작업으로 수행하는 브랜드 운영자
- MD 인력이 부족하거나 상품 기획 역량을 보완하고 싶은 셀러
- 판매·재고 데이터는 있으나 트렌드 데이터와 연결하지 못하는 사업자

## 1.4 사용자 페르소나

### Persona A — 1인 쇼핑몰 운영자
- 상품 소싱과 상세페이지 제작을 혼자 함
- 매일 트렌드를 조사할 시간이 부족함
- “오늘 조사해야 할 상품 후보 5개”를 원함

### Persona B — 브랜드 MD
- 기존 카테고리 내 확장 SKU를 찾고 싶음
- 감이 아닌 데이터와 근거가 필요함
- 공급처와 예상 마진을 함께 보고 싶음

### Persona C — 마케팅 담당자
- 재고/판매 추세를 바탕으로 캠페인을 만들고 싶음
- AI가 타깃·메시지·채널·오퍼를 제안해주길 원함

---

# 2. 범위

## 2.1 MVP In Scope

1. 외부 트렌드/상품 후보 수집
2. 상품 엔티티 정규화 및 중복 제거
3. AI 기반 카테고리/속성 분류
4. 시장성 분석
5. 경쟁 강도 분석
6. 공급처 후보 및 소싱 조건 수집
7. 예상 원가/마진 계산
8. 연결 쇼핑몰의 판매·고객·재고 요약 데이터 수집
9. Shop Fit Score 계산
10. Product Opportunity Score 계산
11. Top N 상품 추천
12. 추천 근거 생성
13. 운영자 승인/거절/보류
14. 승인 상품에 대한 마케팅 전략·카피 초안 생성
15. 실행 로그, 비용, 모델 사용량, 오류 추적
16. 최소 1개 Commerce Adapter 실연동 + 1개 Mock Adapter

## 2.2 MVP Out of Scope

- 자동 구매 발주
- 실제 공급업체와의 계약 체결 자동화
- 무승인 광고비 집행
- 무승인 상품 공개
- 완전 자율 CS
- 자체 결제 시스템
- 자체 물류/풀필먼트
- 모델 파인튜닝
- 복잡한 예측 모델(초기에는 heuristic + statistical features + LLM reasoning으로 시작)
- 범용 브라우저 에이전트가 로그인 후 임의 클릭하는 방식의 운영 자동화

## 2.3 Post-MVP

- 다중 쇼핑몰 플랫폼 동시 연결
- 자동 상품 등록 draft
- 캠페인 draft 생성 및 광고 플랫폼 연결
- A/B 테스트 추천
- 매출 결과를 Product Opportunity Score에 반영하는 feedback loop
- 공급업체 신뢰도 모델
- 사용자별/카테고리별 weight auto-tuning
- Agent Marketplace / Plugin SDK

---

# 3. 설계 철학

## 3.1 Agent는 “판단”, Code는 “계산”

LLM이 적합한 영역:
- 카테고리 분류
- 제품 설명에서 속성 추출
- 트렌드의 원인 해석
- 리뷰/커뮤니티 반응 요약
- 포지셔닝 제안
- 소싱 리스크 설명
- 마케팅 전략/카피 생성

코드가 담당할 영역:
- 가격/환율/배송비 계산
- 마진율 계산
- 점수 가중합
- 중복 판단의 deterministic rule
- 권한 체크
- 재시도 횟수
- 승인 상태
- API rate limiting
- Tenant isolation

## 3.2 Core는 Agent Runtime과 분리

Core Domain은 다음을 몰라야 한다.

- OpenClaw를 쓰는지
- LangGraph를 쓰는지
- 특정 LLM vendor가 무엇인지
- 어떤 채팅 UI에서 호출되는지

Core는 오직 인터페이스 계약을 통해 호출된다.

## 3.3 Side Effect는 별도 Command

읽기/분석과 외부 변경을 분리한다.

- Query: 상품/주문/재고/트렌드 조회
- Command: 상품 등록, 쿠폰 생성, 캠페인 발송, 가격 변경

Command는 기본적으로 approval token을 요구한다.

## 3.4 모든 점수는 설명 가능해야 함

추천 상품에는 반드시 다음이 포함된다.

- 최종 점수
- 구성 요소별 점수
- 사용한 데이터 시점
- 데이터 신뢰도
- 주요 근거 3~5개
- 주요 리스크 1~3개
- “왜 이 쇼핑몰에 적합한지” 설명

---

# 4. 상위 시스템 아키텍처

```text
┌─────────────────────────────────────────────────────────────────────┐
│                        Client / Admin UI                            │
│ Dashboard | Review Queue | Product Detail | Runs | Settings        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ HTTPS
┌───────────────────────────────▼─────────────────────────────────────┐
│                           API Gateway                               │
│ FastAPI | Auth | RBAC | Tenant Context | Rate Limit | Idempotency  │
└──────────────┬─────────────────────┬────────────────────────────────┘
               │                     │
       ┌───────▼────────┐    ┌───────▼─────────────┐
       │ Commerce Core  │    │ Agent/Workflow      │
       │ Domain Service │    │ Orchestrator        │
       └───────┬────────┘    └───────┬─────────────┘
               │                     │
       ┌───────▼─────────────────────▼──────────────┐
       │             Tool / Service Layer            │
       │ Trend | Catalog | Sourcing | Shop | LLM     │
       └───────┬─────────────────────┬──────────────┘
               │                     │
  ┌────────────▼────────────┐   ┌────▼──────────────────┐
  │ Adapter Layer           │   │ Data/Infra            │
  │ Cafe24 / Shopify / Mock │   │ Postgres / Redis/S3   │
  └────────────┬────────────┘   └───────────────────────┘
               │
       External APIs / Commerce Platforms
```

## 4.1 배포 단위

MVP에서는 마이크로서비스로 쪼개지 않는다. **Modular Monolith + Worker** 구조로 시작한다.

- `api`: FastAPI application
- `worker`: background jobs / workflows
- `scheduler`: periodic trend collection
- `postgres`: source of truth
- `redis`: cache, lock, short-lived queue state
- `object storage`: raw documents/snapshots/images if needed

이 구조는 운영 복잡도를 낮추면서 향후 특정 모듈을 서비스로 분리할 수 있다.

---

# 5. 권장 기술 스택

## 5.1 Backend

- Python 3.12+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL 16+
- Redis
- HTTPX
- Tenacity (retry)
- structlog 또는 표준 logging + JSON formatter
- OpenTelemetry

## 5.2 Agent / Workflow

권장 기본:

- LLM Provider abstraction
- LangGraph는 **Agent workflow가 복잡해지는 Phase부터** 사용
- 단순 deterministic workflow는 Python service로 구현

초기 구현 전략:

- Phase 1~4: 일반 Python orchestration
- Phase 5 이후: `AgentRunner` 인터페이스 뒤에 LangGraph 구현 추가
- OpenClaw는 필요할 경우 외부 control surface/운영 인터페이스로 연결 가능하되 Core dependency로 두지 않는다.

## 5.3 Frontend

- Next.js + TypeScript
- 최소 페이지: Dashboard / Candidates / Product Detail / Approval Queue / Runs / Integrations / Settings

MVP에서 프론트엔드 우선순위가 낮으면 API + 단순 Admin UI부터 시작 가능하다.

## 5.4 Testing / Quality

- pytest
- pytest-asyncio
- respx 또는 responses
- factory_boy 또는 자체 fixture factory
- Ruff
- mypy
- pre-commit

## 5.5 Dev Environment

- Docker Compose
- `.env.example`
- Makefile 또는 task runner
- seed command
- mock integrations

---

# 6. 저장소 구조

```text
ai-commerce-agent/
├─ README.md
├─ pyproject.toml
├─ .env.example
├─ docker-compose.yml
├─ Makefile
├─ apps/
│  ├─ api/
│  │  ├─ main.py
│  │  ├─ dependencies.py
│  │  └─ routers/
│  └─ worker/
│     ├─ main.py
│     └─ scheduler.py
├─ src/
│  └─ commerce_agent/
│     ├─ config/
│     ├─ domain/
│     │  ├─ products/
│     │  ├─ trends/
│     │  ├─ sourcing/
│     │  ├─ scoring/
│     │  ├─ shops/
│     │  ├─ marketing/
│     │  ├─ approvals/
│     │  └─ jobs/
│     ├─ application/
│     │  ├─ services/
│     │  ├─ commands/
│     │  ├─ queries/
│     │  └─ workflows/
│     ├─ agents/
│     │  ├─ base.py
│     │  ├─ orchestrator.py
│     │  ├─ trend_agent.py
│     │  ├─ categorizer_agent.py
│     │  ├─ market_agent.py
│     │  ├─ sourcing_agent.py
│     │  ├─ shop_fit_agent.py
│     │  └─ marketing_agent.py
│     ├─ tools/
│     ├─ integrations/
│     │  ├─ commerce/
│     │  │  ├─ base.py
│     │  │  ├─ mock.py
│     │  │  ├─ cafe24.py
│     │  │  └─ shopify.py
│     │  ├─ trend_sources/
│     │  ├─ sourcing_sources/
│     │  └─ llm/
│     ├─ infrastructure/
│     │  ├─ db/
│     │  ├─ cache/
│     │  ├─ queue/
│     │  ├─ telemetry/
│     │  └─ storage/
│     └─ api_schemas/
├─ prompts/
│  ├─ trend/
│  ├─ categorization/
│  ├─ market/
│  ├─ sourcing/
│  ├─ shop_fit/
│  └─ marketing/
├─ tests/
│  ├─ unit/
│  ├─ integration/
│  ├─ contract/
│  ├─ agent_eval/
│  └─ e2e/
├─ scripts/
├─ docs/
│  ├─ IMPLEMENTATION_STATUS.md
│  ├─ API.md
│  ├─ DATA_MODEL.md
│  ├─ RUNBOOK.md
│  └─ adr/
└─ fixtures/
   ├─ trend_sources/
   ├─ suppliers/
   └─ commerce/
```

## 6.1 Dependency Rule

의존 방향은 다음을 지킨다.

```text
API / Agent / Integration
        ↓
Application Service
        ↓
Domain
```

`domain`이 `FastAPI`, `SQLAlchemy`, `LangGraph`, `OpenAI SDK`를 import하면 안 된다.

---

# 7. 핵심 도메인 모델

## 7.1 Tenant

모든 비즈니스 객체의 최상위 소유자.

필드:
- `id: UUID`
- `name: str`
- `status: active|suspended`
- `timezone: str`
- `currency: str`
- `created_at`
- `updated_at`

## 7.2 CommerceConnection

쇼핑몰 플랫폼 연결 정보.

- `id`
- `tenant_id`
- `provider: cafe24|shopify|custom|mock`
- `external_shop_id`
- `display_name`
- `status`
- `credential_ref` (secret 자체를 DB plain text로 저장하지 않음)
- `scopes`
- `last_sync_at`
- `metadata_json`

## 7.3 ProductCandidate

외부에서 발견된 “상품 후보”. 아직 고객 쇼핑몰의 SKU가 아니다.

- `id`
- `tenant_id`
- `canonical_name`
- `brand`
- `category_path`
- `description`
- `attributes_json`
- `primary_image_url`
- `source_count`
- `first_seen_at`
- `last_seen_at`
- `dedupe_key`
- `status: discovered|analyzing|scored|approved|rejected|archived`

## 7.4 ProductSourceObservation

특정 시점/소스에서 관측한 raw-ish 정보.

- `id`
- `tenant_id`
- `candidate_id`
- `source_type`
- `source_name`
- `external_id`
- `url`
- `title_raw`
- `price_raw`
- `currency`
- `review_count`
- `rating`
- `rank`
- `engagement_json`
- `observed_at`
- `raw_payload_ref`

## 7.5 TrendSignal

- `id`
- `tenant_id`
- `candidate_id` nullable
- `keyword`
- `source`
- `metric_name`
- `metric_value`
- `normalized_value`
- `window: 1d|7d|30d|90d`
- `observed_at`

## 7.6 SupplierCandidate

- `id`
- `tenant_id`
- `product_candidate_id`
- `supplier_name`
- `supplier_country`
- `source`
- `product_url`
- `unit_cost`
- `currency`
- `moq`
- `shipping_cost_estimate`
- `lead_time_days_min`
- `lead_time_days_max`
- `supplier_rating`
- `supplier_review_count`
- `data_confidence`
- `last_verified_at`

## 7.7 ShopProductSnapshot

연결된 쇼핑몰의 기존 SKU 스냅샷.

- `id`
- `tenant_id`
- `connection_id`
- `external_product_id`
- `title`
- `category_path`
- `price`
- `cost` nullable
- `inventory_quantity`
- `status`
- `snapshot_at`

## 7.8 SalesAggregate

PII를 최소화하기 위해 MVP에서는 원본 주문보다 집계 데이터를 우선 저장한다.

- `tenant_id`
- `connection_id`
- `external_product_id`
- `date`
- `orders`
- `units`
- `gross_revenue`
- `discount_amount`
- `refund_amount`
- `estimated_cogs`
- `gross_margin`

## 7.9 OpportunityScore

- `id`
- `tenant_id`
- `candidate_id`
- `version`
- `trend_score`
- `demand_score`
- `competition_score`
- `margin_score`
- `supply_score`
- `shop_fit_score`
- `confidence_score`
- `final_score`
- `weights_json`
- `features_json`
- `explanation_json`
- `calculated_at`

## 7.10 Recommendation

- `id`
- `tenant_id`
- `candidate_id`
- `score_id`
- `rank`
- `recommendation_type: source|test|watch|reject`
- `summary`
- `reasons_json`
- `risks_json`
- `recommended_price_range_json`
- `recommended_test_quantity`
- `status: pending|approved|rejected|deferred`
- `created_at`

## 7.11 Approval

- `id`
- `tenant_id`
- `resource_type`
- `resource_id`
- `action`
- `requested_by`
- `requested_at`
- `status`
- `decided_by`
- `decided_at`
- `decision_note`

## 7.12 AgentRun / ToolCall

Agent observability의 핵심 테이블.

`agent_runs`:
- `id`
- `tenant_id`
- `agent_name`
- `agent_version`
- `workflow_name`
- `status`
- `input_json`
- `output_json`
- `prompt_version`
- `model_provider`
- `model_name`
- `input_tokens`
- `output_tokens`
- `estimated_cost`
- `started_at`
- `completed_at`
- `error_code`
- `error_message`
- `correlation_id`

`tool_calls`:
- `id`
- `agent_run_id`
- `tool_name`
- `arguments_json`
- `result_summary_json`
- `status`
- `latency_ms`
- `error_message`

---

# 8. DB 인덱스와 멀티테넌시 규칙

필수 규칙:

1. 모든 tenant-owned table은 첫 인덱스 키에 `tenant_id`를 포함한다.
2. 모든 repository method는 `tenant_id`를 명시적으로 요구한다.
3. `get_by_id(id)` 형태를 금지하고 `get_by_id(tenant_id, id)`를 사용한다.
4. API request 진입 시 Tenant Context를 생성하고 하위 layer에 전달한다.
5. 외부 ID unique constraint는 반드시 tenant/provider scope를 포함한다.

예:

```sql
CREATE UNIQUE INDEX ux_connection_external
ON commerce_connections(tenant_id, provider, external_shop_id);

CREATE INDEX ix_candidate_status_score
ON product_candidates(tenant_id, status, last_seen_at DESC);
```

PostgreSQL RLS는 Phase 10 hardening에서 옵션으로 추가한다.

---

# 9. Commerce Adapter 계약

## 9.1 Interface

```python
class CommerceAdapter(Protocol):
    async def validate_connection(self) -> ConnectionHealth: ...
    async def list_products(self, cursor: str | None = None) -> Page[ExternalProduct]: ...
    async def get_product(self, external_product_id: str) -> ExternalProduct: ...
    async def list_orders(self, start_at: datetime, end_at: datetime, cursor: str | None = None) -> Page[ExternalOrder]: ...
    async def get_inventory(self) -> list[ExternalInventoryItem]: ...
    async def create_product_draft(self, command: CreateProductDraftCommand) -> ExternalMutationResult: ...
    async def update_product_draft(self, command: UpdateProductDraftCommand) -> ExternalMutationResult: ...
```

MVP의 실제 구현은 read-only부터 시작한다.

## 9.2 Adapter Normalized DTO

플랫폼마다 API shape가 달라도 Application Layer에는 동일 DTO를 반환한다.

```python
class ExternalProduct(BaseModel):
    external_id: str
    title: str
    description: str | None
    category_path: list[str]
    price: Decimal
    currency: str
    cost: Decimal | None
    inventory_quantity: int | None
    status: str
    created_at: datetime | None
    updated_at: datetime | None
```

## 9.3 Adapter Error Taxonomy

- `AuthError`
- `RateLimitError`
- `PermissionError`
- `NotFoundError`
- `ExternalValidationError`
- `TransientExternalError`
- `PermanentExternalError`

Retry는 `RateLimitError`, `TransientExternalError`에만 적용한다.

---

# 10. Trend Source Adapter 계약

```python
class TrendSource(Protocol):
    name: str
    async def discover(self, query: TrendQuery) -> list[RawTrendItem]: ...
```

`TrendQuery`:
- category filters
- locale
- time window
- max results
- exclude terms

`RawTrendItem`:
- source
- source_id
- title
- url
- observed_metrics
- price if available
- image if available
- published/observed time
- raw metadata

MVP에서는 source 2종만 연결해도 된다. 단, Fixture 기반 Mock Source는 반드시 먼저 구현한다.

## 10.1 수집 정책

- 공식 API가 있으면 API 우선
- 서비스 약관을 위반하는 크롤링 금지
- robots/rate limit 준수
- Raw payload는 필요한 최소 기간만 보관
- Source별 request budget 설정

---

# 11. 상품 정규화 및 중복 제거

## 11.1 Pipeline

```text
Raw Item
  → Text cleanup
  → Brand/model extraction
  → Attribute extraction
  → Category classification
  → Candidate key generation
  → Exact/near duplicate search
  → Merge or create candidate
```

## 11.2 Dedupe Strategy

1차 deterministic:
- normalized brand + normalized model number
- GTIN/UPC/EAN 등 표준 식별자 존재 시 우선
- normalized title token overlap

2차 semantic:
- embedding similarity 또는 LLM adjudication

3차 safety rule:
- 서로 다른 variation(색상/용량)과 서로 다른 제품 모델을 구분

`dedupe_key` 예:

```text
brand|model|category|critical_attributes_hash
```

## 11.3 Merge Rule

Candidate에는 canonical 정보만 유지하고 source별 값은 Observation에 남긴다. 원본을 덮어쓰지 않는다.

---

# 12. 카테고리화

## 12.1 Category Taxonomy

MVP는 고정 taxonomy JSON을 repo에 versioned asset으로 둔다.

예:

```json
{
  "version": "2026-01",
  "categories": [
    {
      "id": "home.kitchen.drinkware",
      "label_ko": "주방 > 음료용품",
      "allowed_attributes": ["material", "capacity_ml", "insulated"]
    }
  ]
}
```

## 12.2 Categorizer Output

```json
{
  "category_id": "home.kitchen.drinkware",
  "confidence": 0.91,
  "attributes": {
    "material": "stainless_steel",
    "capacity_ml": 600,
    "insulated": true
  },
  "reason": "..."
}
```

confidence < threshold이면 `needs_review=true`.

---

# 13. Agent 설계

멀티에이전트를 쓰되 “에이전트 수를 늘리는 것” 자체가 목표가 아니다. 각 Agent는 명확한 책임과 I/O 계약을 가져야 한다.

## 13.1 Orchestrator Agent

**책임:** 전체 workflow의 단계 결정.  
**입력:** tenant, workflow goal, current state.  
**출력:** next action 또는 final recommendation set.  
**허용 Tool:** workflow state 조회, 하위 agent 호출.  
**금지:** 직접 외부 쇼핑몰 변경.

MVP에서는 상당 부분 deterministic state machine으로 구현하고, LLM orchestration은 제한적으로 사용한다.

## 13.2 Trend Discovery Agent

**목적:** 유망 키워드/상품 후보 발굴.

입력:
- tenant category preference
- exclusion list
- source observations

출력:
- candidate proposals[]
- trend explanation
- confidence

Tool:
- trend search
- candidate lookup
- source fetch

## 13.3 Categorizer Agent

**목적:** 상품 taxonomy와 속성 정규화.

출력은 반드시 schema validation을 통과해야 한다.

## 13.4 Market Analyst Agent

**목적:** 수요, 경쟁, 가격대, 소비자 반응을 해석.

출력:
- `demand_assessment`
- `competition_assessment`
- `price_band`
- `positive_signals[]`
- `negative_signals[]`
- `market_risks[]`
- `confidence`

## 13.5 Sourcing Agent

**목적:** 공급처 후보 비교 및 소싱 리스크 설명.

출력:
- supplier candidates ranking
- landed cost assumptions
- MOQ/lead time risk
- suggested verification checklist

중요: 공급처 정보가 불충분하면 “추정”을 사실처럼 출력하지 않는다.

## 13.6 Shop Fit Agent

**목적:** 고객 쇼핑몰의 기존 판매 특성과 신규 후보의 궁합 평가.

입력은 개인정보가 아니라 집계 feature를 기본으로 한다.

예:
- category revenue share
- ASP distribution
- repeat purchase tendency
- best seller attributes
- seasonality
- stock turnover

출력:
- fit score features
- reason
- cannibalization risk
- cross-sell opportunity

## 13.7 Marketing Agent

승인된 후보에 대해서만 실행.

출력:
- target segment proposal
- positioning
- offer
- channel strategy
- 3 copy variants
- landing/detail page key messages
- prohibited/uncertain claims list

MVP는 “draft 생성”까지만 수행한다.

---

# 14. Agent Structured Output 규칙

모든 Agent output은 다음 공통 envelope를 가진다.

```json
{
  "schema_version": "1.0",
  "confidence": 0.0,
  "summary": "",
  "facts": [],
  "inferences": [],
  "risks": [],
  "missing_data": [],
  "result": {}
}
```

규칙:

- `facts`: tool/source에서 직접 얻은 사실
- `inferences`: LLM이 해석한 내용
- `missing_data`: 추가 검증 필요 항목
- confidence는 data quality를 고려해 보수적으로 책정

---

# 15. Product Opportunity Score

## 15.1 MVP Score

최종 점수는 0~100.

기본 weight:

- Trend: 0.20
- Demand: 0.15
- Competition: 0.15
- Margin: 0.15
- Supply: 0.10
- Shop Fit: 0.20
- Confidence: 0.05

```text
FinalScore =
  Trend*0.20 +
  Demand*0.15 +
  Competition*0.15 +
  Margin*0.15 +
  Supply*0.10 +
  ShopFit*0.20 +
  Confidence*0.05
```

**주의:** Competition은 “경쟁이 적을수록 높은 점수”로 정규화한 값이다.

## 15.2 Trend Score

추천 feature:
- 7d growth
- 30d growth
- source diversity
- acceleration
- recency

예시:

```text
trend_raw =
  0.35 * growth_7d_norm +
  0.25 * growth_30d_norm +
  0.15 * acceleration_norm +
  0.15 * source_diversity_norm +
  0.10 * recency_norm
```

## 15.3 Demand Score

- search/engagement level
- review velocity proxy
- sales rank if available
- intent signal

## 15.4 Competition Score

- competing product count inverse
- seller concentration inverse
- ad saturation inverse
- price compression inverse

## 15.5 Margin Score

먼저 landed cost를 계산한다.

```text
landed_cost = unit_cost + shipping + duties + expected_payment_fee + expected_fulfillment_cost
```

```text
contribution_margin = selling_price - landed_cost - variable_platform_fee - expected_discount - expected_refund_cost
```

```text
margin_rate = contribution_margin / selling_price
```

MVP는 margin rate를 threshold piecewise function으로 0~100 정규화한다.

예:
- <= 5% → 0
- 10% → 25
- 20% → 60
- 30% → 85
- >= 40% → 100

정확한 threshold는 tenant 설정 가능.

## 15.6 Supply Score

- supplier count
- MOQ suitability
- lead time
- supplier rating/confidence
- cost dispersion
- stock availability

## 15.7 Shop Fit Score

핵심 차별화 점수.

Feature:
- category affinity
- target ASP fit
- attribute similarity to winners
- cross-sell potential
- customer profile fit
- season fit
- inventory cannibalization penalty

MVP는 deterministic features + LLM explanation 조합으로 시작한다.

## 15.8 Confidence Score

데이터가 부족한데 점수가 높게 나오는 문제를 막는다.

요소:
- source count
- source diversity
- freshness
- price confidence
- supplier verification
- shop data coverage

## 15.9 Hard Reject Rules

FinalScore보다 먼저 적용한다.

예:
- 예상 마진율 < tenant minimum
- 공급처 없음
- 규제/금지 카테고리
- 데이터 신뢰도 < minimum
- 경쟁가격 대비 예상판매가 비현실적

Hard Reject는 코드로 구현한다.

---

# 16. Workflow 1 — Daily Product Discovery

## 16.1 Trigger

- schedule: tenant별 1일 1회 또는 수동 실행
- input: category scope, max candidates

## 16.2 State

```python
class DiscoveryWorkflowState(BaseModel):
    tenant_id: UUID
    job_id: UUID
    correlation_id: UUID
    categories: list[str]
    raw_items: list[str]  # ids
    candidate_ids: list[UUID]
    analyzed_ids: list[UUID]
    scored_ids: list[UUID]
    recommendation_ids: list[UUID]
    errors: list[WorkflowError]
```

## 16.3 Steps

1. load tenant configuration
2. run trend sources in parallel
3. persist raw observations
4. normalize raw items
5. dedupe/merge candidates
6. categorize candidates
7. filter excluded/restricted candidates
8. enrich market signals
9. find supplier candidates
10. fetch shop aggregate profile
11. calculate deterministic features
12. run market/shop-fit interpretation
13. calculate Opportunity Score
14. apply hard reject rules
15. rank candidates
16. create Top N recommendations
17. persist run summary
18. notify UI

## 16.4 Retry Policy

- source timeout: exponential backoff, max 3
- LLM parse failure: retry with repair prompt, max 2
- permanent validation error: do not retry
- workflow step failure: mark partial; continue only if downstream data requirements satisfied

## 16.5 Acceptance

- 동일 fixture 입력에 ranking 결과가 deterministic threshold 범위 내에서 재현됨
- 단일 source failure가 전체 workflow를 죽이지 않음
- Agent output parse error가 DB에 corrupt data를 남기지 않음
- recommendation마다 score breakdown 존재

---

# 17. Workflow 2 — Recommendation Review

```text
pending recommendation
    ↓
operator review
  ├─ approve
  ├─ reject
  └─ defer
```

Approve 시:
- marketing draft workflow 실행 가능
- future phase에서는 product draft 생성 가능

Reject 시:
- rejection reason 저장
- feedback feature로 활용

승인 기록은 수정 불가능한 audit event로 남긴다.

---

# 18. Workflow 3 — Marketing Draft

입력:
- approved recommendation
- tenant brand profile
- channel preference
- existing best-performing messages summary(optional)

단계:
1. 상품 key benefit 추출
2. target segment 정의
3. positioning 생성
4. offer 제안
5. channel별 copy 생성
6. claim risk 검사
7. operator review queue에 저장

출력 schema:

```json
{
  "positioning": "",
  "target_segments": [],
  "offer": {},
  "channels": {
    "instagram": {"copies": []},
    "email": {"subject_lines": [], "body_outline": []},
    "product_page": {"headline": "", "bullets": []}
  },
  "claims_to_verify": [],
  "risks": []
}
```

---

# 19. Prompt 관리

## 19.1 Prompt는 코드에 inline으로 박지 않는다

파일:

```text
prompts/<agent>/<prompt_name>/<version>.md
```

예:

```text
prompts/market/analyze_candidate/v1.md
```

DB/AgentRun에는 `prompt_name`, `prompt_version`, `prompt_hash` 저장.

## 19.2 Prompt Template 구성

각 prompt는 다음 섹션을 갖는다.

1. Role
2. Objective
3. Input Contract
4. Available Facts
5. Rules
6. Forbidden Behavior
7. Output Schema
8. Confidence Guidance

## 19.3 Hallucination 방지 규칙

- tool result에 없는 supplier credential을 만들지 말 것
- 수치를 추정할 경우 `assumption`으로 명시
- source가 부족하면 `missing_data`에 넣을 것
- 제품의 법적/의학적 효능을 임의 생성하지 말 것
- 정확한 가격·재고는 observation timestamp와 함께 다룰 것

---

# 20. LLM Provider Abstraction

```python
class LLMClient(Protocol):
    async def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[BaseModel],
        temperature: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> BaseModel: ...
```

추가 요구:
- timeout
- retry
- usage capture
- cost estimation
- trace id
- redaction hook
- model routing

Provider-specific object를 Domain에 노출하지 않는다.

---

# 21. Tool 설계

모든 tool은 명확한 입력/출력 schema를 갖는다.

예:

```python
class SearchTrendToolInput(BaseModel):
    query: str
    category: str | None
    window_days: int = 30
    limit: int = 20

class SearchTrendToolOutput(BaseModel):
    items: list[TrendSearchResult]
    source: str
    fetched_at: datetime
```

Tool에는 다음 metadata를 둔다.

- name
- version
- read_only
- side_effect_level
- timeout
- max_result_size

`side_effect_level`:
- `none`
- `draft_only`
- `external_mutation`

AgentRunner는 `external_mutation` tool 실행 전 approval을 검증한다.

---

# 22. API 설계

Base path: `/api/v1`

## 22.1 Auth / Tenant

- `GET /me`
- `GET /tenants/{tenant_id}`

## 22.2 Integrations

- `POST /integrations/commerce`
- `GET /integrations/commerce`
- `POST /integrations/commerce/{id}/validate`
- `POST /integrations/commerce/{id}/sync`
- `DELETE /integrations/commerce/{id}`

## 22.3 Discovery

- `POST /discovery-runs`
- `GET /discovery-runs/{id}`
- `GET /discovery-runs/{id}/candidates`

Request:

```json
{
  "categories": ["home.kitchen"],
  "max_candidates": 50,
  "source_names": ["mock_trend_a", "mock_trend_b"]
}
```

Response:

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

## 22.4 Candidates

- `GET /candidates`
- `GET /candidates/{id}`
- `GET /candidates/{id}/observations`
- `GET /candidates/{id}/suppliers`
- `GET /candidates/{id}/score`

## 22.5 Recommendations

- `GET /recommendations`
- `GET /recommendations/{id}`
- `POST /recommendations/{id}/approve`
- `POST /recommendations/{id}/reject`
- `POST /recommendations/{id}/defer`

Approve Request:

```json
{
  "note": "샘플 20개 테스트 진행",
  "action_scope": ["generate_marketing_draft"]
}
```

## 22.6 Marketing

- `POST /recommendations/{id}/marketing-draft`
- `GET /marketing-drafts/{id}`

## 22.7 Runs / Observability

- `GET /agent-runs`
- `GET /agent-runs/{id}`
- `GET /jobs/{id}`

---

# 23. Background Job 상태 모델

상태:

```text
queued → running → succeeded
               ↘ failed
               ↘ partial
queued → cancelled
```

모든 job에:
- progress percent
- current step
- completed steps
- warning count
- error count

Worker가 죽어도 job이 orphan되지 않도록 heartbeat/lease를 둔다.

---

# 24. Event 모델

내부 이벤트 예:

- `commerce.connection.created`
- `commerce.sync.completed`
- `trend.discovery.started`
- `candidate.created`
- `candidate.enriched`
- `candidate.scored`
- `recommendation.created`
- `recommendation.approved`
- `marketing.draft.created`
- `agent.run.failed`

MVP는 DB outbox pattern으로 이벤트 유실을 막는다.

`outbox_events`:
- id
- tenant_id
- event_type
- aggregate_type
- aggregate_id
- payload_json
- created_at
- published_at
- attempt_count

---

# 25. 설정 모델

Tenant 설정은 versioned JSON 또는 typed tables로 관리한다.

예:

```json
{
  "discovery": {
    "categories": ["home.kitchen"],
    "max_daily_candidates": 50,
    "excluded_keywords": []
  },
  "scoring": {
    "minimum_margin_rate": 0.15,
    "minimum_confidence": 50,
    "weights": {
      "trend": 0.2,
      "demand": 0.15,
      "competition": 0.15,
      "margin": 0.15,
      "supply": 0.1,
      "shop_fit": 0.2,
      "confidence": 0.05
    }
  },
  "approval": {
    "require_human_for_external_mutation": true
  }
}
```

설정 validation을 Pydantic model로 강제한다.

---

# 26. 쇼핑몰 프로필(Shop Intelligence Profile)

Shop Fit의 기반이 되는 집계 객체.

```python
class ShopIntelligenceProfile(BaseModel):
    generated_at: datetime
    sales_window_days: int
    category_revenue_share: dict[str, float]
    category_unit_share: dict[str, float]
    asp_percentiles: dict[str, Decimal]
    top_product_attributes: dict[str, Any]
    repeat_purchase_proxy: float | None
    inventory_turnover_by_category: dict[str, float]
    seasonality_features: dict[str, float]
    data_coverage: float
```

MVP에서는 매일 또는 sync 후 재계산.

---

# 27. Sourcing 비용 모델

## 27.1 Landed Cost

```python
landed_cost = (
    supplier_unit_cost
    + per_unit_shipping
    + per_unit_duty
    + per_unit_import_tax_estimate
    + payment_fee_estimate
    + inbound_handling_estimate
)
```

모든 항목은 `actual|quoted|estimated|unknown` 상태를 가진다.

## 27.2 Pricing Scenario

각 candidate에 최소 3개 scenario:
- conservative
- base
- optimistic

예:

```json
{
  "base": {
    "selling_price": 39000,
    "landed_cost": 16000,
    "platform_fee": 3900,
    "expected_discount": 2000,
    "expected_refund_cost": 800,
    "contribution_margin": 16300,
    "margin_rate": 0.418
  }
}
```

Unknown cost가 많으면 confidence score를 낮춘다.

---

# 28. 규제/금지 상품 Guard

Agent가 상품을 추천하기 전에 code-level guard를 통과한다.

초기 `RestrictedCategoryPolicy` 인터페이스:

```python
class RestrictedCategoryPolicy(Protocol):
    def evaluate(self, candidate: ProductCandidate) -> PolicyDecision: ...
```

`PolicyDecision`:
- allowed
- requires_manual_review
- blocked
- reasons[]

정책은 국가/플랫폼별로 분리 가능해야 한다.

MVP에서는 최소한 configured denylist + manual review list를 제공한다.

---

# 29. 인증/권한

역할:
- `owner`
- `admin`
- `analyst`
- `operator`
- `viewer`

권한 예:
- analyst: discovery 실행, 분석 열람
- operator: approve/reject 가능
- admin: integration 연결
- owner: billing/security

API layer에서 RBAC 체크. Domain service에서도 sensitive command는 방어적으로 권한 context를 검증한다.

---

# 30. Secret 관리

원칙:
- API token을 application log에 출력 금지
- DB에는 secret raw value 저장 금지
- secret manager/KMS 또는 encrypted credential store 사용
- access token refresh가 필요한 provider는 별도 credential service에서 처리
- webhook signature secret 분리

개발 환경에서는 `.env` 사용 가능하지만 `.env` commit 금지.

---

# 31. PII / 개인정보 최소화

MVP에서 추천 기능에 필요한 데이터는 상품/판매 집계 중심으로 설계한다.

- 고객 이메일/전화번호를 Agent prompt에 넣지 않는다.
- 주문 원본이 필요하면 즉시 집계 후 원본 저장을 최소화한다.
- Agent trace에는 민감정보 redaction 적용.
- 사용자 요청 시 tenant 데이터 삭제 workflow 제공.

---

# 32. Observability

## 32.1 Trace

모든 request/job/agent/tool call을 `correlation_id`로 연결한다.

Span 예:

```text
POST /discovery-runs
  └─ discovery_workflow
     ├─ trend_source.fetch
     ├─ candidate.normalize
     ├─ agent.market_analysis
     │  └─ llm.generate
     ├─ supplier.lookup
     ├─ scoring.calculate
     └─ recommendation.persist
```

## 32.2 Metrics

필수:
- discovery_runs_total
- discovery_run_duration_seconds
- candidates_discovered_total
- candidates_recommended_total
- external_api_errors_total
- llm_calls_total
- llm_tokens_total
- llm_cost_total
- structured_output_parse_failures_total
- approval_rate
- recommendation_rejection_rate
- source_freshness_seconds

## 32.3 Cost Guard

tenant별:
- daily LLM spend limit
- monthly LLM spend limit
- per workflow max token budget
- per candidate max enrichment budget

Budget 초과 시 degrade mode:
- 하위 모델
- 후보 수 축소
- 일부 설명 생성 생략

---

# 33. 캐시

캐시 가능한 데이터:
- category taxonomy
- exchange rates snapshot
- supplier lookup result short TTL
- trend source response short TTL
- shop intelligence profile

캐시하면 안 되는 것:
- approval state
- job source of truth
- audit log

Cache key에는 tenant/data version을 포함한다.

---

# 34. 오류 처리

모든 API error는 표준 envelope:

```json
{
  "error": {
    "code": "INTEGRATION_RATE_LIMITED",
    "message": "External commerce provider rate limit exceeded",
    "retryable": true,
    "correlation_id": "..."
  }
}
```

내부 exception을 그대로 사용자에게 노출하지 않는다.

Error code namespace:
- `AUTH_*`
- `VALIDATION_*`
- `INTEGRATION_*`
- `AGENT_*`
- `WORKFLOW_*`
- `SCORING_*`
- `APPROVAL_*`

---

# 35. Idempotency

외부 변경 API는 `Idempotency-Key`를 요구한다.

서버는:
- tenant + key + route + body hash 저장
- 동일 요청 재호출 시 이전 결과 반환
- 같은 key에 다른 body면 409

Webhook 처리도 provider event id로 dedupe.

---

# 36. Test Strategy

## 36.1 Unit Test

대상:
- margin 계산
- score normalization
- hard reject rule
- dedupe key
- category mapping
- permission logic

조건:
- 외부 network 없음
- LLM 없음

## 36.2 Integration Test

- Postgres repository
- migrations
- Redis lock
- Mock Commerce Adapter
- Mock Trend Source

## 36.3 Contract Test

각 Adapter는 동일 test suite를 통과해야 한다.

```python
class CommerceAdapterContract:
    async def test_list_products_returns_normalized_dto(...): ...
    async def test_rate_limit_maps_to_standard_error(...): ...
```

## 36.4 Agent Eval

Golden dataset을 `tests/agent_eval/cases/*.json`으로 관리.

평가 항목:
- schema pass rate
- category accuracy
- factual consistency
- unsupported claim rate
- risk detection
- explanation usefulness

LLM eval 결과는 deterministic CI gate와 분리한다. 단, 최소 schema pass rate는 CI gate로 둘 수 있다.

## 36.5 E2E

Scenario:
1. mock shop 연결
2. fixture sales sync
3. discovery run
4. candidate 생성
5. score 계산
6. top recommendation 생성
7. approve
8. marketing draft 생성
9. trace 확인

---

# 37. Seed / Fixture 전략

반드시 외부 API 없이 전체 workflow를 실행할 수 있어야 한다.

Fixture set:

- `trend_hot_tumbler.json`
- `trend_flat_product.json`
- `trend_high_competition.json`
- `supplier_good_margin.json`
- `supplier_no_supplier.json`
- `shop_profile_home_lifestyle.json`
- `shop_profile_low_asp.json`

`make seed` 실행 시 demo tenant와 demo shop을 생성한다.

---

# 38. CI/CD

PR gate:

```text
ruff check
mypy
pytest unit
pytest integration
migration check
security scan
```

main merge 후:
- container build
- migration dry-run
- staging deploy
- smoke test

production:
- backward-compatible migration 우선
- expand/contract migration pattern
- feature flag로 위험 기능 배포

---

# 39. 환경 분리

환경:
- local
- test
- staging
- production

외부 side effect:
- local/test: mock only
- staging: sandbox/draft only
- production: approval required

`ENVIRONMENT`에 따라 보안 규칙을 완화하지 말고, 가능한 기능 자체를 제한한다.

---

# 40. Admin UI 화면 명세

## 40.1 Dashboard

표시:
- 오늘 발견 후보 수
- 추천 수
- 승인 대기 수
- 평균 Opportunity Score
- 최근 run 상태
- 비용 사용량

## 40.2 Candidates

필터:
- category
- score range
- status
- risk
- supplier availability
- source

컬럼:
- product
- category
- trend
- margin
- shop fit
- final score
- confidence
- status

## 40.3 Candidate Detail

탭:
1. Summary
2. Trend Evidence
3. Market
4. Suppliers
5. Shop Fit
6. Score Breakdown
7. Agent Trace

## 40.4 Approval Queue

카드에 반드시:
- 왜 추천했는지
- 가장 큰 리스크
- 예상 가격/마진
- 공급처 상태
- 승인/거절/보류

## 40.5 Runs

- workflow
- started/completed
- duration
- token/cost
- errors
- trace

---

# 41. MVP UX 원칙

AI가 “정답”을 말하는 UI보다 “의사결정 자료”를 제공하는 UI를 만든다.

나쁜 표현:
- “이 상품은 반드시 잘 팔립니다.”

좋은 표현:
- “현재 데이터 기준 Opportunity Score 82점. 최근 7일 성장률과 쇼핑몰 카테고리 적합도는 높지만 공급처 검증 수준이 낮습니다.”

---

# 42. 구현 Phase 개요

```text
Phase 0  Repo & Engineering Baseline
Phase 1  Domain + Database
Phase 2  Mock Integrations + Sync
Phase 3  Trend Ingestion + Candidate Normalization
Phase 4  Deterministic Scoring Foundation
Phase 5  LLM/Agent Foundation
Phase 6  Market + Sourcing + Shop Fit
Phase 7  End-to-End Discovery Workflow
Phase 8  Approval + Marketing Draft
Phase 9  Real Commerce Adapter
Phase 10 Security/Observability/Hardening
Phase 11 Minimal Admin UI
Phase 12 Pilot Readiness
```

---

# 43. Phase 0 — Repo & Engineering Baseline

## 목표

프로젝트가 재현 가능하게 실행되고 품질 gate를 가진다.

## Tasks

### P0-01 Repository 생성
- 위 repository structure 생성
- Python package 설정
- README 작성

### P0-02 Tooling
- Ruff
- mypy
- pytest
- pre-commit

### P0-03 Config
- typed settings
- `.env.example`
- dev/test/prod config 분리

### P0-04 Docker Compose
- API
- worker placeholder
- Postgres
- Redis

### P0-05 Health API
- `GET /health/live`
- `GET /health/ready`

### P0-06 CI
- lint/type/test

## Acceptance Criteria

```bash
make bootstrap
make lint
make typecheck
make test
make dev
```

모두 성공. `/health/ready`가 DB/Redis 상태를 확인한다.

---

# 44. Phase 1 — Domain + Database

## Tasks

### P1-01 Domain entities
Tenant, Connection, Candidate, Observation, Supplier, Score, Recommendation, Approval, Job, AgentRun.

### P1-02 Repository interfaces
Domain/Application layer에 Protocol 정의.

### P1-03 SQLAlchemy models
Domain entity와 DB model을 직접 동일 객체로 쓰지 않아도 된다. mapping layer를 권장.

### P1-04 Alembic initial migration
모든 core table 생성.

### P1-05 Tenant context
API dependency와 repository enforcement.

### P1-06 Audit fields
created_at/updated_at/created_by 등 일관성 확보.

## Acceptance Criteria

- migration up/down test 통과
- tenant A에서 tenant B entity 조회 불가
- repository unit/integration test 통과
- UTC storage, tenant timezone presentation rule 문서화

---

# 45. Phase 2 — Mock Integrations + Shop Sync

## Tasks

### P2-01 CommerceAdapter Protocol
계약 정의.

### P2-02 MockCommerceAdapter
fixture 기반 상품/주문/재고 제공.

### P2-03 Sync service
- products sync
- sales aggregate sync
- inventory snapshot sync

### P2-04 ShopIntelligenceProfile builder
판매 집계에서 profile 생성.

### P2-05 Integration API
connect/list/validate/sync.

## Acceptance Criteria

- 외부 network 없이 demo shop sync 가능
- sync를 두 번 실행해도 duplicate가 생기지 않음
- profile이 fixture의 기대값과 일치

---

# 46. Phase 3 — Trend Ingestion + Candidate Normalization

## Tasks

### P3-01 TrendSource Protocol
### P3-02 MockTrendSource A/B
### P3-03 Raw observation persistence
### P3-04 Normalizer
텍스트/브랜드/모델명 기본 정규화.

### P3-05 Taxonomy
versioned taxonomy.

### P3-06 Dedupe
exact + fuzzy rule.

### P3-07 Candidate creation
source observations 여러 개가 한 candidate에 merge 가능.

## Acceptance Criteria

- fixture 100개에서 의도된 canonical candidate 수가 생성됨
- 같은 fixture 재실행 시 candidate 수가 증가하지 않음
- source provenance 추적 가능

---

# 47. Phase 4 — Deterministic Scoring Foundation

## Tasks

### P4-01 Feature models
TrendFeatures, DemandFeatures, CompetitionFeatures, MarginFeatures, SupplyFeatures, ShopFitFeatures, ConfidenceFeatures.

### P4-02 Normalizers
각 feature 0~100 변환 함수.

### P4-03 Cost model
Landed cost / contribution margin.

### P4-04 Hard reject rules
### P4-05 OpportunityScoreCalculator
### P4-06 Versioned scoring config

## Acceptance Criteria

- score 계산에는 LLM 호출 없음
- 동일 입력→동일 점수
- weight 합이 1이 아니면 validation error
- boundary case test 포함

---

# 48. Phase 5 — LLM/Agent Foundation

## Tasks

### P5-01 LLMClient Protocol
### P5-02 Provider implementation 1종
### P5-03 Structured output wrapper
### P5-04 Prompt registry
### P5-05 AgentRunner
### P5-06 AgentRun/ToolCall logging
### P5-07 Cost budget guard
### P5-08 FakeLLMClient
테스트용 deterministic response.

## Acceptance Criteria

- 실제 provider 없이 agent test 가능
- malformed output repair test 존재
- prompt version이 run에 기록됨
- token/cost 기록됨
- budget exceed 시 명확한 error/degrade behavior

---

# 49. Phase 6 — Market, Sourcing, Shop Fit Agent

## Tasks

### P6-01 CategorizerAgent
### P6-02 MarketAnalystAgent
### P6-03 SourcingAgent
### P6-04 ShopFitAgent
### P6-05 Agent schemas
### P6-06 Tool allowlist
### P6-07 confidence/missing_data rules

## Acceptance Criteria

- 모든 output schema validation 통과
- unsupported claim eval 존재
- source 없을 때 supplier를 만들어내지 않음
- shop PII를 prompt에 넣지 않음

---

# 50. Phase 7 — End-to-End Discovery Workflow

## Tasks

### P7-01 Workflow state model
### P7-02 Job service
### P7-03 step orchestration
### P7-04 partial failure
### P7-05 parallelization
Trend sources / candidate enrichment 중 safe parallel 처리.

### P7-06 ranking/recommendation service
### P7-07 run summary
### P7-08 scheduler

## Acceptance Criteria

`make demo-discovery` 하나로:

1. demo tenant 생성
2. shop fixture sync
3. trend fixture ingest
4. candidates 생성
5. market/sourcing/shop-fit enrichment
6. score 계산
7. Top 5 recommendation 생성
8. JSON/DB 결과 출력

전체가 실행되어야 한다.

---

# 51. Phase 8 — Approval + Marketing Draft

## Tasks

### P8-01 Approval domain
### P8-02 Approval API
### P8-03 immutable audit event
### P8-04 MarketingAgent
### P8-05 claim risk output
### P8-06 approval-gated workflow

## Acceptance Criteria

- pending recommendation만 승인 가능
- 승인 전 marketing draft 생성 정책을 config로 제어
- external mutation tool은 approval 없으면 실행 불가
- audit log 삭제/수정 불가 application rule

---

# 52. Phase 9 — Real Commerce Adapter

우선 하나만 완성한다. 사업 타깃에 따라 Cafe24 또는 Shopify를 선택한다.

## Tasks

### P9-01 OAuth/token lifecycle
### P9-02 connection validation
### P9-03 read product sync
### P9-04 read order/sales sync
### P9-05 inventory sync
### P9-06 rate limit handling
### P9-07 webhook/event support(optional MVP)
### P9-08 contract suite 통과

## Acceptance Criteria

- real sandbox/test store에서 read sync 성공
- secret log leakage 없음
- rate limit retry가 bounded
- provider outage 시 core 데이터가 손상되지 않음

---

# 53. Phase 10 — Security / Observability / Hardening

## Tasks

### P10-01 RBAC
### P10-02 Secret store
### P10-03 Trace + metrics
### P10-04 PII redaction
### P10-05 retry/dead letter strategy
### P10-06 outbox
### P10-07 idempotency
### P10-08 rate limiting
### P10-09 optional DB RLS
### P10-10 backup/restore runbook

## Acceptance Criteria

- tenant isolation security test
- injected secret이 log에 나오지 않음
- failed workflow traceable
- duplicate webhook safe
- restore drill 문서 존재

---

# 54. Phase 11 — Minimal Admin UI

## Tasks

### P11-01 auth shell
### P11-02 dashboard
### P11-03 candidates list/detail
### P11-04 recommendation queue
### P11-05 approve/reject UI
### P11-06 runs UI
### P11-07 integrations settings

## Acceptance Criteria

운영자가 UI만으로:
- shop 연결 상태 확인
- discovery 실행
- Top 5 확인
- 근거/리스크 열람
- approve/reject
- marketing draft 확인
- 실패 run 추적

가능해야 한다.

---

# 55. Phase 12 — Pilot Readiness

## Tasks

### P12-01 feature flags
### P12-02 tenant onboarding
### P12-03 sample scoring presets
### P12-04 support/admin tooling
### P12-05 cost dashboard
### P12-06 data retention policy
### P12-07 terms/compliance checklist
### P12-08 pilot feedback capture

## Pilot Success Metrics

제품 지표:
- 추천 클릭/열람률
- 승인률
- 추천→샘플 소싱 전환율
- 추천→실제 상품 등록 전환율
- 추천 상품의 30일 판매 성과
- operator time saved

시스템 지표:
- workflow success rate
- P95 run duration
- cost per discovery run
- agent parse failure rate
- source failure rate

---

# 56. 첫 4주 구현 계획

## Week 1

- Phase 0 전부
- Phase 1 핵심 entity/repository/migration
- Mock tenant setup

산출물:
- 실행 가능한 API
- DB schema
- tenant isolation test

## Week 2

- Phase 2
- Mock shop sync
- ShopIntelligenceProfile
- Phase 3 trend fixture ingestion 시작

산출물:
- fixture 기반 shop 데이터
- 외부 trend item → candidate 흐름

## Week 3

- Phase 3 완료
- Phase 4 scoring
- Recommendation read API

산출물:
- LLM 없이도 후보→점수→ranking 가능

## Week 4

- Phase 5 LLM foundation
- Categorizer/Market Agent 최소 버전
- end-to-end demo 연결

산출물:
- `make demo-discovery`

이 시점에서 제품 가설을 실제 화면/JSON으로 검증한다.

---

# 57. Codex 작업 단위 템플릿

각 작업은 다음 양식을 사용한다.

```markdown
## Task ID: P4-05
### Goal
OpportunityScoreCalculator를 구현한다.

### Inputs
- Feature score 7종
- tenant scoring config

### Outputs
- OpportunityScore domain object

### Constraints
- LLM 호출 금지
- Decimal 사용 영역 명확화
- weight 합 1.0 validation

### Files
- src/commerce_agent/domain/scoring/models.py
- src/commerce_agent/application/services/scoring.py
- tests/unit/scoring/test_calculator.py

### Tests
- normal case
- zero score
- max score
- invalid weight
- missing feature

### Done When
- unit tests pass
- mypy pass
- ruff pass
- docs/IMPLEMENTATION_STATUS.md updated
```

---

# 58. Codex가 매 Task 완료 시 남겨야 할 보고

1. 변경 파일
2. 구현 내용 요약
3. 설계와 다른 결정이 있었는지
4. 테스트 목록과 결과
5. migration 여부
6. 보안 영향
7. 다음 Task에 필요한 전제

예:

```text
Task P4-05 completed.
Changed:
- ...
Tests:
- 14 passed
Design deviation:
- None
Next prerequisite:
- P4-06 scoring config versioning
```

---

# 59. 금지되는 구현 패턴

Codex는 다음을 하지 않는다.

- 하나의 2,000줄짜리 `agent.py`에 모든 로직 작성
- Agent prompt에서 직접 SQL 생성 후 실행
- tenant_id 없는 repository call
- LLM이 계산한 마진율을 그대로 저장
- 외부 API response를 validation 없이 DB에 저장
- token/API key를 log에 출력
- prompt를 Python string 곳곳에 복사
- provider별 API shape를 domain model에 노출
- 테스트에서 실제 외부 API 호출
- `except Exception: pass`
- 무한 retry
- side effect tool을 승인 없이 호출
- “AI가 알아서 판단”이라는 이유로 business rule을 prompt 안에만 숨김

---

# 60. ADR 후보

초기에 문서화해야 할 결정:

- ADR-0001 Modular Monolith
- ADR-0002 Core/Agent Separation
- ADR-0003 Multi-Tenancy Strategy
- ADR-0004 Commerce Adapter Contract
- ADR-0005 Structured LLM Output Only
- ADR-0006 Deterministic Scoring
- ADR-0007 Human Approval for External Mutation
- ADR-0008 Prompt Versioning
- ADR-0009 Job/Workflow Runtime Choice
- ADR-0010 Raw Data Retention Policy

---

# 61. OpenClaw / LangGraph 사용 위치

## 61.1 OpenClaw

선택적 역할:
- 운영자가 자연어로 “오늘 상품 조사 실행” 요청
- Manager Agent UI/채널
- 내부 운영 자동화

하지만 다음은 OpenClaw에 넣지 않는다.
- authoritative business state
- scoring engine
- tenant permissions
- commerce credential source of truth

## 61.2 LangGraph

사용 시점:
- workflow가 단순 함수 호출을 넘어 조건 분기/루프/재질문/부분 실패가 많아질 때

LangGraph node는 application service/tool을 호출하고 DB를 직접 만지지 않는다.

## 61.3 결론

```text
OpenClaw = optional control surface
LangGraph = optional agent workflow engine
Commerce Core = product IP / source of truth
Adapters = platform expansion layer
```

---

# 62. 상용 패키지 확장 구조

고객마다 코드를 fork하지 않는다.

멀티테넌트 SaaS + Adapter/Plugin 구조:

```text
Tenant A ─┐
Tenant B ─┼─> Commerce Core ─> Adapter Registry ─> Cafe24
Tenant C ─┘                       ├──────────────> Shopify
                                 └──────────────> Custom
```

추후 Plugin SDK:

```python
class CommercePlugin(Protocol):
    manifest: PluginManifest
    def commerce_adapter(self) -> CommerceAdapter | None: ...
    def trend_sources(self) -> list[TrendSource]: ...
    def sourcing_sources(self) -> list[SourcingSource]: ...
```

Plugin manifest에 required permissions와 data scope를 선언한다.

---

# 63. 비즈니스 모델과 기술 설계 연결

가능한 요금제는 기술적으로 quota로 표현한다.

예:

### Starter
- 1 shop
- daily 1 discovery
- 30 candidates/day
- 1 user

### Growth
- 3 shops
- 200 candidates/day
- sourcing + marketing draft
- team roles

### Pro
- multiple shops
- custom scoring weights
- API access
- higher run budget

Quota는 `tenant_entitlements`로 관리한다.

---

# 64. Feedback Loop

Pilot 이후 가장 중요한 고도화.

Recommendation outcome:
- approved?
- sampled?
- sourced?
- listed?
- sales after 7/30/90 days
- margin actual
- return rate

이 결과를 feature store/analytics에 저장한다.

초기에는 자동 학습보다 offline 분석으로 weight를 조정한다.

```text
Recommendation
   ↓
Actual Outcome
   ↓
Feature/Score comparison
   ↓
Weight calibration
   ↓
Scoring version N+1
```

Scoring version 변경 시 과거 score를 덮어쓰지 않는다.

---

# 65. 데이터 신뢰도 설계

각 값은 가능하면 provenance를 가진다.

예:

```json
{
  "value": 12.5,
  "unit": "USD",
  "source": "supplier_api",
  "observed_at": "2026-08-19T00:00:00Z",
  "quality": "quoted"
}
```

quality:
- verified
- quoted
- observed
- estimated
- inferred
- unknown

LLM inference 값은 `inferred`를 넘어설 수 없다.

---

# 66. 상품 추천 Explainability Schema

Recommendation detail에서 최소 다음 JSON을 생성한다.

```json
{
  "headline": "홈리빙 고객군과 높은 적합도를 보이는 보온 텀블러 후보",
  "why_now": [
    "최근 7일 추세 상승",
    "복수 소스에서 동시 관측"
  ],
  "why_this_shop": [
    "기존 주방 카테고리 매출 비중 높음",
    "현재 ASP 구간과 예상 판매가 일치"
  ],
  "economics": {
    "base_margin_rate": 0.31,
    "cost_confidence": 0.72
  },
  "risks": [
    "공급처 리드타임 검증 필요"
  ],
  "next_action": "샘플 10~20개 검토"
}
```

---

# 67. Performance Targets (MVP)

- 일반 API P95 < 500ms (외부 API 없는 read)
- discovery workflow 50 candidates: 목표 < 10분, hard limit 30분
- candidate detail read P95 < 1초
- Agent structured output success > 98% after bounded repair
- workflow success > 95% excluding external provider outage

이 숫자는 초기 목표이며 실측 후 조정한다.

---

# 68. Capacity Assumption

Pilot:
- tenants: 10~50
- discovery runs: 100/day 이하
- candidates: 10k~100k
- observations: 1M 이하

이 수준에서는 Postgres 단일 클러스터와 worker pool로 충분한 설계를 유지한다. premature sharding 금지.

---

# 69. 운영 Runbook 최소 항목

`docs/RUNBOOK.md`에:

- DB migration 실패 대응
- worker stuck job 처리
- 외부 API rate limit 대응
- credential revoke 대응
- LLM provider outage degrade mode
- tenant data export/delete
- rollback 절차
- 비용 급증 대응

---

# 70. Definition of MVP Done

MVP는 “AI가 대화한다”가 아니라 아래 business loop가 실제로 닫힐 때 완료다.

```text
Shop 연결
  ↓
판매/재고 데이터 동기화
  ↓
외부 트렌드 수집
  ↓
상품 후보 정규화/카테고리화
  ↓
시장성/공급처/Shop Fit 분석
  ↓
Opportunity Score
  ↓
Top N 추천
  ↓
사람 승인
  ↓
마케팅 Draft
```

필수 품질 조건:

- Mock 환경 E2E 자동화
- 실제 쇼핑몰 Adapter 1종 read sync
- Tenant isolation
- Agent trace/cost
- approval gate
- score explainability
- repeatable deployment
- 최소 운영 UI

---

# 71. Codex 첫 실행 지시문

Codex에게 이 문서를 제공한 뒤 첫 요청은 아래처럼 한다.

```text
이 문서를 프로젝트의 authoritative implementation spec으로 사용하라.
먼저 Phase 0만 구현하라. Phase 1 이후 기능은 구현하지 마라.

작업 전:
1. 전체 문서를 읽고 dependency rule과 금지 패턴을 요약한다.
2. Phase 0에서 생성/수정할 파일 목록을 제안한다.
3. 기존 repo가 있다면 현재 구조와 충돌을 확인한다.

작업 중:
- 작은 commit 가능한 단위로 구현한다.
- 모든 public interface에 type annotation을 작성한다.
- 테스트를 함께 작성한다.

작업 후:
- lint/typecheck/test를 실행한다.
- docs/IMPLEMENTATION_STATUS.md를 갱신한다.
- 변경 파일, 테스트 결과, 설계 deviation, 다음 prerequisite를 보고한다.

Phase 0 Acceptance Criteria를 충족하지 못하면 Phase 1로 넘어가지 마라.
```

---

# 72. Phase별 Codex 프롬프트 템플릿

```text
Authoritative spec: docs/AI_Commerce_Agent_Implementation_Spec.md
Current phase: Phase X
Allowed scope: PX-01 ~ PX-NN only

1. 현재 구현 상태를 검사하라.
2. 이번 phase acceptance criteria와 gap을 표로 정리하라.
3. dependency order대로 task를 실행하라.
4. 설계와 충돌하는 기존 코드가 있으면 임의로 우회하지 말고 ADR 초안을 작성하라.
5. 각 task마다 테스트를 추가하라.
6. 모든 테스트를 실행하라.
7. acceptance criteria를 항목별 PASS/FAIL로 보고하라.
8. FAIL이 하나라도 있으면 다음 phase를 구현하지 마라.
```

---

# 73. 최종 구현 우선순위

사업 검증 관점에서 가장 중요한 순서는 다음이다.

1. **Shop Intelligence Profile** — “우리 쇼핑몰을 이해”하는 기반
2. **Trend/Candidate Pipeline** — 외부에서 무엇이 뜨는지 수집
3. **Opportunity Score** — 일관된 평가
4. **Supplier Economics** — 실제 돈이 남는지 확인
5. **Explainable Recommendation** — 운영자가 믿고 판단 가능
6. **Approval Feedback** — 추천 품질 개선 신호
7. **Marketing Draft** — 승인된 상품을 팔기 위한 다음 단계
8. **실제 플랫폼 Adapter 확장**

초기 개발에서 Marketing Agent를 화려하게 만드는 것보다 1~5를 정확하게 만드는 것이 우선이다.

---

# 74. 구현 시작 시 최종 체크리스트

- [ ] Python/DB/Redis 개발 환경이 한 명령으로 뜨는가?
- [ ] tenant_id 없는 데이터 접근이 구조적으로 어려운가?
- [ ] 모든 외부 시스템은 adapter interface 뒤에 있는가?
- [ ] 외부 API 없이 fixture로 E2E가 가능한가?
- [ ] LLM 없이 score 계산이 가능한가?
- [ ] LLM output은 schema validation 되는가?
- [ ] prompt가 version 관리되는가?
- [ ] agent/tool call이 trace 되는가?
- [ ] 추천의 점수 근거를 사용자가 볼 수 있는가?
- [ ] 공급처/가격 데이터의 시점과 신뢰도를 기록하는가?
- [ ] 외부 변경은 승인 없이 불가능한가?
- [ ] 실제 플랫폼 1종의 read sync가 가능한가?
- [ ] 실패한 workflow가 재시도/추적 가능한가?
- [ ] 비용 제한이 있는가?
- [ ] 파일럿 고객의 결과 feedback을 저장할 구조가 있는가?

---

# 75. 결론

본 시스템의 핵심 IP는 “여러 Agent를 많이 만드는 것”이 아니다. 핵심은 다음 네 가지의 결합이다.

1. **Market Intelligence:** 외부에서 뜨는 상품을 빠르게 발견하는 데이터 파이프라인
2. **Shop Intelligence:** 특정 쇼핑몰의 고객·가격대·카테고리·판매 특성을 이해하는 프로필
3. **Commerce Economics:** 공급가·물류·수수료·할인·반품을 포함한 실제 수익성 계산
4. **Decision Workflow:** 설명 가능한 점수와 리스크를 기반으로 사람이 승인하고 결과를 다시 학습 데이터로 축적하는 운영 루프

따라서 구현도 이 네 가지를 중심으로 진행하고, OpenClaw/LangGraph/LLM provider는 교체 가능한 실행 도구로 취급한다.

**첫 번째 성공 기준은 “AI가 멋진 문장을 생성하는가”가 아니라, 운영자가 매일 Top 5 추천을 보고 실제 샘플 소싱 여부를 판단할 만큼 근거가 정확하고 일관적인가이다.**
