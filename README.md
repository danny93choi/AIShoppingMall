# AI Commerce Agent

트렌드 상품 발굴부터 쇼핑몰 적합도 분석, 설명 가능한 추천과 승인 워크플로까지 제공하는
멀티테넌트 AI Commerce Agent 플랫폼입니다. 현재 구현 범위는 Phase 0 engineering baseline입니다.

## 요구 사항

- Python 3.12+
- Docker 및 Docker Compose
- Make

## 로컬 설정

```bash
cp .env.example .env
make bootstrap
make lint
make typecheck
make test
make dev
```

API는 `http://localhost:8000`에서 실행됩니다.

- `GET /health/live`: 프로세스 생존 확인
- `GET /health/ready`: PostgreSQL 및 Redis 의존성 확인

Phase 2에서는 `/api/v1/integrations/commerce` 아래에 fixture 기반 mock shop 연결 및 동기화
API가 제공됩니다. API 계약은 `docs/API.md`를 참고하세요.

Phase 3에서는 `/api/v1/trends/mock-ingest`로 100개의 fixture trend observation을 수집하고,
정규화 및 중복 제거를 거쳐 다섯 개 canonical candidate로 병합할 수 있습니다.

## NAVER 실제 쇼핑 트렌드

NAVER Cloud Platform의 NAVER API HUB에서 발급한 인증 정보를 `.env`에 설정하면 관리자
화면에서 쇼핑인사이트의 실제 한국 쇼핑 클릭 추이를 조사할 수 있습니다.

```env
NAVER_API_HUB_CLIENT_ID=
NAVER_API_HUB_CLIENT_SECRET=
NAVER_SEARCH_AD_API_KEY=
NAVER_SEARCH_AD_SECRET_KEY=
NAVER_SEARCH_AD_CUSTOMER_ID=
```

연결만 확인하는 읽기 전용 smoke test는 `make naver-trend-smoke`로 실행합니다. 관리자 화면
`http://localhost:8000/admin`에서는 자동 발굴 또는 키워드 최대 20개 직접 비교를 실행할 수
있습니다. `NAVER REAL` 표시는 API HUB에서 수집한 실제 데이터라는 의미입니다.
트렌드 지수는 절대 검색량이 아닌 선택 기간 내 상대적 클릭 비율입니다.


## 구조와 의존성

이 저장소는 API와 worker를 함께 배포 가능한 modular monolith로 유지합니다.

```text
API / Agent / Integration
        ↓
Application Service
        ↓
Domain
```

Domain은 FastAPI, SQLAlchemy, agent runtime 또는 LLM SDK에 의존하지 않습니다. 외부 시스템은
adapter/service interface 뒤에 두며 외부 변경은 승인 없이 실행하지 않습니다.

## 환경

`ENVIRONMENT`는 `local`, `test`, `staging`, `production`만 허용합니다. 비밀값은 `.env`에 두되
저장소에 커밋하지 않습니다. Docker Compose 기본 자격증명은 로컬 개발 전용입니다.
