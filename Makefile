COMPOSE ?= docker compose

.PHONY: bootstrap dev up down logs seed ingest ingest-radar format lint typecheck test test-web test-python build contracts check

bootstrap:
	corepack enable
	pnpm install --frozen-lockfile
	uv sync --all-packages --dev --frozen

dev:
	pnpm dev

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f api web

seed:
	$(COMPOSE) --profile maintenance run --rm census-loader

ingest:
	$(COMPOSE) --profile live-ingestion up --build ingestion

ingest-radar:
	$(COMPOSE) --profile radar run --rm mrms-ingestion

format:
	pnpm -r --if-present format
	uv run ruff format apps services

lint:
	pnpm lint
	uv run ruff check apps services

typecheck:
	pnpm typecheck
	uv run mypy apps/api services/ingestion

test: test-python test-web

test-python:
	uv run pytest

test-web:
	pnpm test

contracts:
	pnpm api:generate

build:
	pnpm build

check:
	$(MAKE) lint
	$(MAKE) typecheck
	$(MAKE) test
	$(MAKE) build
