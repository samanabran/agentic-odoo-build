COMPOSE         = docker compose --env-file .env -f infra/docker-compose.yml
ODOO_CONTAINER  = $(shell docker ps -qf "name=odoo")
ORCH_CONTAINER  = $(shell docker ps -qf "name=orchestrator")
DB_CONTAINER    = $(shell docker ps -qf "name=db")

.PHONY: up up-private down logs shell-odoo shell-orch \
        test eval seed reindex lint

# ── Stack ─────────────────────────────────────────────────────────────────────

up:
	$(COMPOSE) up -d

up-private:
	$(COMPOSE) --profile private up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

shell-odoo:
	docker exec -it $(ODOO_CONTAINER) bash

shell-orch:
	docker exec -it $(ORCH_CONTAINER) bash

# ── Quality ───────────────────────────────────────────────────────────────────

test:
	cd orchestrator && python -m pytest tests/ -v --cov=app --cov-report=term-missing

lint:
	cd orchestrator && python -m ruff check app/ eval/ tests/ && \
	  python -m mypy app/ --ignore-missing-imports

# ── Eval harness ─────────────────────────────────────────────────────────────

eval:
	cd orchestrator && python -m eval.runner

# ── Data ─────────────────────────────────────────────────────────────────────

seed:
	python scripts/seed_demo.py

reindex:
	python scripts/reindex.py
