.PHONY: install dev test format lint up down

install:  ## Install backend dev dependencies
	pip install -r backend/requirements/dev.txt

dev:  ## Run the API locally with autoreload
	cd backend && uvicorn api.main:app --reload

test:  ## Run the test suite
	cd backend && pytest

format:  ## Auto-format (isort + black)
	cd backend && isort . && black .

lint:  ## Check formatting and lint (ruff + isort + black)
	cd backend && ruff check . && isort --check-only . && black --check .

up:  ## Start local services (postgres + redis)
	docker compose up -d

down:  ## Stop local services
	docker compose down
