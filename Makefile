.PHONY: help install test test-backend test-frontend lint build dev clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install all dependencies
	cd backend && uv sync
	cd frontend && npm install

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && uv run pytest tests/ -v

test-frontend: ## Run frontend tests
	cd frontend && npm run test -- --run

lint: ## Lint and format code
	cd backend && uv run ruff check src/ tests/
	cd frontend && npm run lint

build: ## Build production artifacts
	cd frontend && npm run build

dev-backend: ## Start backend dev server
	cd backend && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend: ## Start frontend dev server
	cd frontend && npm run dev

clean: ## Clean build artifacts
	rm -rf backend/.venv backend/__pycache__
	rm -rf frontend/node_modules frontend/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
