# HarnessFlow developer Makefile
# Targets are scaffolded; bodies will be implemented as the corresponding code lands.

.PHONY: help up down logs proto demo eval test lint fmt clean tools-check

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start the full local dev stack (docker-compose).
	@echo "TODO(week-1): docker compose up -d && wait-for healthchecks"

down: ## Stop the dev stack.
	@echo "TODO(week-1): docker compose down"

logs: ## Tail logs from the dev stack.
	@echo "TODO(week-1): docker compose logs -f"

proto: ## Regenerate proto/JSON-schema clients (Go, Python, TS). Idempotent.
	@echo "TODO(week-1): buf generate && datamodel-codegen ..."

demo: ## Run the canonical research-assistant demo workflow end-to-end.
	@echo "TODO(week-4): scripts/demo.sh"

eval: ## Run the eval suite against the current main workflow.
	@echo "TODO(week-7): cd apps/eval-runner && uv run harnessflow_eval --suite research-assistant"

demo-bandit: ## (Week 13) A/B compare learned-retry vs static-retry policies.
	@echo "TODO(week-13): scripts/demo-bandit.sh"

test: ## Run unit + integration tests across all apps.
	@echo "TODO: go test ./... && uv run pytest && pnpm test"

lint: ## Run linters across all apps.
	@echo "TODO: golangci-lint run && ruff check && pnpm lint"

fmt: ## Format code in-place across all apps.
	@echo "TODO: gofmt && ruff format && pnpm format"

tools-check: ## Verify required local tooling is installed.
	@command -v go >/dev/null || { echo "missing: go"; exit 1; }
	@command -v docker >/dev/null || { echo "missing: docker"; exit 1; }
	@command -v terraform >/dev/null || { echo "missing: terraform"; exit 1; }
	@command -v helm >/dev/null || { echo "missing: helm"; exit 1; }
	@command -v buf >/dev/null || { echo "missing: buf"; exit 1; }
	@command -v uv >/dev/null || { echo "missing: uv"; exit 1; }
	@command -v node >/dev/null || { echo "missing: node"; exit 1; }
	@echo "all required tools installed"

clean: ## Remove generated artifacts (does not touch source).
	@echo "TODO: clean build/test artifacts"
