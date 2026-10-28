.PHONY: seed api web test dev install

install:
	uv sync
	cd frontend && npm install

seed:
	uv run python -m backend.seed_demo

api:
	uv run uvicorn backend.app:app --reload --port 8000

web:
	cd frontend && npm run dev

test:
	uv run pytest -q

dev:
	uv run python -m scripts.dev
