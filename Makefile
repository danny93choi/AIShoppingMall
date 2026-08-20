PYTHON ?= python3.12
VENV := .venv
BIN := $(VENV)/bin

.PHONY: bootstrap lint format typecheck test migrate migrate-down dev down logs demo-discovery shopify-smoke

bootstrap:
	@$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 12), "Python 3.12+ is required"'
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/pip install -e '.[dev]'
	@if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then \
		$(BIN)/pre-commit install; \
	else \
		echo "Skipping pre-commit hook installation: not a Git worktree"; \
	fi

lint:
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

typecheck:
	$(BIN)/mypy

test:
	$(BIN)/pytest

migrate:
	$(BIN)/alembic upgrade head

migrate-down:
	$(BIN)/alembic downgrade base

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs --follow api worker

demo-discovery:
	docker compose up -d postgres redis
	docker compose run --build --rm api sh -c "alembic upgrade head && python -m apps.demo_discovery"

shopify-smoke:
	docker compose run --build --rm api python -m apps.shopify_smoke
