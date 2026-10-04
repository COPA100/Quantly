.PHONY: install dev test format lint up down seed engine engine-wheel loadtest

install:  ## Install backend dev dependencies
	pip install -r backend/requirements/dev.txt

engine:  ## Build and install the C++ engine (pybind11) into the current env
	python engine/scripts/build_wheel.py

engine-wheel:  ## Build the C++ engine wheel into engine/dist without installing
	python engine/scripts/build_wheel.py --no-install

dev:  ## Run the API locally with autoreload
	cd backend && uvicorn api.main:app --reload

test:  ## Run the test suite
	cd backend && pytest && pytest ../infra/lambda

format:  ## Auto-format (isort + black)
	cd backend && isort . && black .

lint:  ## Check formatting and lint (ruff + isort + black)
	cd backend && ruff check . && isort --check-only . && black --check .

up:  ## Start local services (postgres + redis)
	docker compose up -d

down:  ## Stop local services
	docker compose down

seed:  ## Create the demo account and an analyzed sample portfolio (API_URL=... for a deployed stack)
	cd backend && python -m scripts.seed --api-url $(or $(API_URL),http://localhost:8000)

LOADTEST_COMPOSE = docker compose -f docker-compose.yml -f loadtest/docker-compose.loadtest.yml
SCENARIO ?= burst
WORKERS ?= 2
BOOK ?= warm
K6_BASE_URL ?= http://host.docker.internal:8000

loadtest:  ## Run a k6 scenario on the pinned compose stack (SCENARIO=burst|steady|ramp WORKERS=2 BOOK=warm|cold)
	$(LOADTEST_COMPOSE) up -d --build --wait --scale worker=$(WORKERS) postgres redis s3 api worker beat
	mkdir -p loadtest/results
	docker run --rm -i --add-host host.docker.internal:host-gateway -v "$(CURDIR)":/work -w /work \
		-e BASE_URL=$(K6_BASE_URL) -e SCENARIO=$(SCENARIO) -e WORKERS=$(WORKERS) -e BOOK=$(BOOK) \
		-e SUMMARY_PATH=/work/loadtest/results/$(SCENARIO)-$(BOOK)-$(WORKERS)w.json \
		grafana/k6 run /work/loadtest/k6.js
	@if [ "$(SCENARIO)" = "burst" ]; then python loadtest/capacity.py loadtest/results/burst-*.json; fi
