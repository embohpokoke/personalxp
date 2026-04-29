.PHONY: db-up db-down db-local-create migrate seed-check dev smoke

PYTHON ?= .venv/bin/python

db-up:
	docker compose up -d db

db-down:
	docker compose down

db-local-create:
	createdb personal_xp_local || true

migrate:
	$(PYTHON) scripts/migrate_local.py

seed-check:
	$(PYTHON) scripts/check_seed.py

dev:
	$(PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port 8004 --reload

smoke:
	$(PYTHON) scripts/smoke_local.py
