.DEFAULT_GOAL := help
.PHONY: help up down setup db migrate dev api web test test-api test-web lint format demo

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-10s %s\n", $$1, $$2}'

up: ## Run everything in Docker on http://localhost:8000
	docker compose up --build

down: ## Stop the Docker containers (your data is kept)
	docker compose down

setup: ## Install the Python and Node dependencies for local development
	uv sync
	cd frontend && npm ci

db: ## Start only Postgres, in Docker
	docker compose up -d --wait db

migrate: ## Apply database migrations
	uv run alembic upgrade head

dev: db migrate ## Postgres in Docker, plus the API and web app with live reload
	@echo "Open http://localhost:5173"
	@trap 'kill 0' INT TERM EXIT; $(MAKE) --no-print-directory api & $(MAKE) --no-print-directory web & wait

api: ## Run the API with auto-reload on :8000
	uv run uvicorn app.main:app --reload --port 8000

web: ## Run the web app dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

test: test-api test-web ## Run all tests

test-api: ## Run the Python tests (SQLite; set TEST_DATABASE_URL for Postgres)
	uv run pytest

test-web: ## Run the web app tests
	cd frontend && npm test

lint: ## Check formatting, lint and types
	uv run ruff check .
	uv run ruff format --check .
	cd frontend && npm run typecheck

format: ## Format the Python code
	uv run ruff check --fix .
	uv run ruff format .

demo: ## Add the hand-written demo course (no API key needed)
	uv run marginalia demo
