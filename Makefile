.PHONY: up down dev fetch ingest stats inspect eval test lint dump

up:            ## Postgres + embedding server (local)
	docker compose --profile ml up -d --wait

down:
	docker compose --profile ml down

dev:
	uv run uvicorn app.main:app --reload

fetch:
	uv run python -m scripts.fetch_corpus

ingest:        ## make ingest [ID=axa-lu-optihome]
	uv run python -m scripts.ingest $(ID)

stats:
	uv run python -m scripts.stats

inspect:       ## make inspect ID=axa-lu-optihome
	uv run python -m scripts.stats $(ID)

eval:          ## make eval [CONTRAT=axa-lu-optihome]
	uv run python -m scripts.run_eval $(CONTRAT)

test:
	uv run pytest -q

lint:
	uv run ruff check . && uv run ruff format --check . && uv run mypy app

dump:          ## database snapshot to restore on the VM (docs/DEPLOIEMENT.md)
	docker compose exec -T postgres pg_dump -U sinistre -Fc sinistre > data/sinistre.dump
