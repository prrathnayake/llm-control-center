.PHONY: install dev test lint format run docker-up docker-down

install:
	python -m pip install -e .[dev]

dev:
	uvicorn llm_control_center.app:app --reload --host 0.0.0.0 --port 8080

test:
	pytest

lint:
	ruff check src tests

format:
	ruff format src tests
	ruff check --fix src tests

run:
	uvicorn llm_control_center.app:app --host 0.0.0.0 --port 8080

docker-up:
	docker compose up --build

docker-down:
	docker compose down
