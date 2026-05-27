# HarnessFlow developer Makefile
# Targets are scaffolded; bodies will be implemented as the corresponding code lands.

.PHONY: help up down logs ps restart nuke proto sqlc migrate-up migrate-down migrate-status demo eval eval-gate demo-bandit test lint fmt clean tools-check

COMPOSE := docker compose

help: ## Show this help.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

up: ## Start the full local dev stack (docker-compose).
	$(COMPOSE) up -d
	@echo ""
	@echo "stack starting. UIs:"
	@echo "  Temporal     http://localhost:8233"
	@echo "  Jaeger       http://localhost:16686"
	@echo "  Prometheus   http://localhost:9090"
	@echo "  Grafana      http://localhost:3000"
	@echo "  MinIO        http://localhost:9001  (harnessflow / harnessflow)"
	@echo ""
	@echo "run 'make ps' to watch health, 'make logs' to tail."

down: ## Stop the dev stack (keeps volumes).
	$(COMPOSE) down

logs: ## Tail logs from the dev stack.
	$(COMPOSE) logs -f

ps: ## Show dev stack container status.
	$(COMPOSE) ps

restart: ## Restart the dev stack.
	$(COMPOSE) restart

nuke: ## Stop the dev stack AND delete all volumes (destructive).
	$(COMPOSE) down -v

# Pinned codegen tool versions — keep these stable so `make proto` is
# reproducible and CI's `git diff --exit-code` check stays meaningful.
DATAMODEL_CODEGEN_VERSION := 0.57.0
GO_JSONSCHEMA_VERSION := v0.23.1
SCHEMA := packages/sdk/schema/workflow.schema.json
GEN_GO := packages/sdk/gen/go
GEN_PY := packages/sdk/gen/python

# Local-dev DATABASE_URL — matches docker-compose.yml. CI overrides this.
DATABASE_URL ?= postgres://harnessflow:harnessflow@localhost:5432/harnessflow?sslmode=disable
API_MIGRATIONS := apps/api/migrations

proto: ## Regenerate proto + JSON-schema clients (Go, Python, TS). Idempotent.
	@echo ">> buf lint"
	buf lint
	@echo ">> buf generate (Go + Connect, Python, TypeScript)"
	buf generate
	@echo ">> go mod tidy (generated Go module)"
	cd $(GEN_GO) && go mod tidy
	@echo ">> Pydantic models from JSON schema"
	uvx --from 'datamodel-code-generator==$(DATAMODEL_CODEGEN_VERSION)' datamodel-codegen \
		--input $(SCHEMA) --input-file-type jsonschema \
		--output $(GEN_PY)/workflow_schema.py \
		--output-model-type pydantic_v2.BaseModel \
		--use-double-quotes --target-python-version 3.12 --disable-timestamp
	@echo ">> Go structs from JSON schema"
	go run github.com/atombender/go-jsonschema@$(GO_JSONSCHEMA_VERSION) \
		-p schema --output $(GEN_GO)/schema/workflow.go $(SCHEMA)
	@echo ">> sync TS clients into the dashboard"
	rm -rf apps/dashboard/src/gen
	mkdir -p apps/dashboard/src/gen
	cp -R packages/sdk/gen/ts/harnessflow/* apps/dashboard/src/gen/
	@echo ">> codegen complete — packages/sdk/gen/ + apps/dashboard/src/gen/ in sync"

sqlc: ## Regenerate sqlc bindings for apps/api.
	cd apps/api && sqlc generate
	@echo ">> sqlc complete"

migrate-up: ## Apply all pending Postgres migrations.
	migrate -path $(API_MIGRATIONS) -database "$(DATABASE_URL)" up

migrate-down: ## Roll back the most recent migration.
	migrate -path $(API_MIGRATIONS) -database "$(DATABASE_URL)" down 1

migrate-status: ## Print current migration version.
	migrate -path $(API_MIGRATIONS) -database "$(DATABASE_URL)" version

demo: ## Run the canonical research-assistant demo workflow end-to-end.
	bash scripts/demo.sh

eval: ## Run the eval suite against a workflow id (set HARNESSFLOW_WORKFLOW_ID).
	@test -n "$$HARNESSFLOW_WORKFLOW_ID" || { echo "set HARNESSFLOW_WORKFLOW_ID=<uuid>" >&2; exit 1; }
	uv run --directory apps/eval-runner harnessflow-eval --workflow-id $$HARNESSFLOW_WORKFLOW_ID --dataset $${HARNESSFLOW_DATASET:-research-assistant}

eval-gate: ## Run the CI eval-gate against locally changed workflow YAMLs (api+worker must be up).
	uv run --directory apps/eval-runner python $(CURDIR)/scripts/ci-eval-gate.py \
		--changed-files $$(git diff --name-only origin/main...HEAD -- 'packages/examples/workflows/*.yaml') \
		--out-md /tmp/eval-gate-comment.md

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
