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
