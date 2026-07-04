.PHONY: install dev test format lint up down

install:  ## Install backend dev dependencies
	pip install -r backend/app/requirements/dev.txt

dev:  ## Run the API locally with autoreload
	cd backend/app && uvicorn main:app --reload

test:  ## Run the test suite
	cd backend && pytest

format:  ## Auto-format (isort + black)
	cd backend && isort app && black app

lint:  ## Check formatting and lint (ruff + isort + black)
	cd backend && ruff check app && isort --check-only app && black --check app

up:  ## Start local services (postgres + redis)
	docker compose up -d

down:  ## Stop local services
	docker compose down
