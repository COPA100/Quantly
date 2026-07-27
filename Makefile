.PHONY: install dev test format lint up down engine engine-wheel

install:  ## Install backend dev dependencies
	pip install -r backend/requirements/dev.txt

engine:  ## Build and install the C++ engine (pybind11) into the current env
	python engine/scripts/build_wheel.py

engine-wheel:  ## Build the C++ engine wheel into engine/dist without installing
	python engine/scripts/build_wheel.py --no-install

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
