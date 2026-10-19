SHELL := /bin/bash
COMPOSE := docker compose

.PHONY: help up down logs ps build rebuild seed test test-backend psql clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Build (if needed) and start the full stack
	$(COMPOSE) up -d --build

down: ## Stop the stack (keeps volumes/data)
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

ps: ## Show service status
	$(COMPOSE) ps

build: ## Build images without starting
	$(COMPOSE) build

rebuild: ## Force a clean rebuild of backend and frontend
	$(COMPOSE) build --no-cache backend frontend

seed: ## (Re)seed the demo tenant if the DB is empty
	$(COMPOSE) exec backend python -m scripts.seed_demo

test-backend: ## Run backend unit tests inside the container
	$(COMPOSE) exec backend sh -c "pip install -q -r requirements-dev.txt && python -m pytest -q"

test-e2e: ## Run the cross-tenant isolation E2E test against the running stack
	bash scripts/e2e.sh

psql: ## Open a psql shell on the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER:-budget} -d $${POSTGRES_DB:-budget}

clean: ## Stop the stack and delete all data volumes (destructive)
	$(COMPOSE) down -v
