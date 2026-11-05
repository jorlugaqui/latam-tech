# Single entry point for every project command. Only Docker is required.
COMPOSE := docker compose
API_DEV := $(COMPOSE) --profile dev run --rm api-dev
MOCK_DEV := $(COMPOSE) --profile dev run --rm mock-tools-dev
ARGS    ?=
# Docker Desktop (macOS) briefly caches "file not found" on bind mounts, so a module created
# right after its failing test (TDD) can stay invisible. Walking the tree refreshes it.
REFRESH := find src tests migrations -name '*.py' > /dev/null

.DEFAULT_GOAL := help
.PHONY: help env up down clean logs migrate migration smoke test lint format check check-mock-tools

help: ## List available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

up: ## Build and start the stack, waiting until every service is healthy
	$(COMPOSE) up -d --build --wait

down: ## Stop the stack (keeps the database volume)
	$(COMPOSE) down

clean: ## Stop the stack and delete the database volume
	$(COMPOSE) down -v

logs: ## Follow logs; pick services with ARGS="api fe"
	$(COMPOSE) logs -f $(ARGS)

migrate: ## Apply migrations (alembic upgrade head) and print the current revision
	$(COMPOSE) run --rm migrate sh -c "alembic upgrade head && alembic current"

smoke: ## Smoke-check the running stack (headers, proxy, internal paths, rate limit)
	./scripts/smoke.sh

migration: ## Autogenerate a revision: make migration name=add_x (stack must be up)
	@if [ -z "$(name)" ]; then echo 'usage: make migration name=<slug>' >&2; exit 1; fi
	$(API_DEV) alembic revision --autogenerate -m "$(name)"

env: ## Create .env from .env.example with random secrets (never overwrites)
	@if [ -f .env ]; then echo ".env already exists; refusing to overwrite it" >&2; exit 1; fi
	@umask 077; sed \
		-e "s|^API_TOKEN=.*|API_TOKEN=$$(openssl rand -hex 32)|" \
		-e "s|^TOOLS_API_TOKEN=.*|TOOLS_API_TOKEN=$$(openssl rand -hex 32)|" \
		-e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$$(openssl rand -hex 24)|" \
		.env.example > .env
	@echo "Created .env with random secrets"

test: ## Run unit tests; pass pytest arguments with ARGS="..."
	$(API_DEV) sh -c "$(REFRESH) && pytest $(ARGS)"

lint: ## ruff (lint + format check) and import-linter layer contracts
	$(API_DEV) sh -c "$(REFRESH) && ruff check . && ruff format --check . && lint-imports"

format: ## Format and auto-fix with ruff
	$(API_DEV) sh -c "ruff format . && ruff check --fix ."

check: lint test check-mock-tools ## lint + tests (api and mock-tools)

check-mock-tools: ## ruff + unit tests for the mock-tools service
	$(MOCK_DEV) sh -c "find src tests -name '*.py' > /dev/null && ruff check . && ruff format --check . && pytest"
