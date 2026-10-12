# HarnessFlow developer Makefile
# Targets are scaffolded; bodies will be implemented as the corresponding code lands.

.PHONY: help dev setup install-skills up down logs ps restart nuke proto sqlc migrate-up migrate-down migrate-status demo eval eval-gate events-consume demo-bandit test lint typecheck build check fmt clean tools-check helm-sync-migrations helm-deps helm-lint helm-template kind-up kind-down kind-load

COMPOSE := docker compose
.DEFAULT_GOAL := help
PYTHON_APPS := worker eval-runner event-consumer

dev: ## Start local PRD harness (frozen dependencies, DB, migrations, API, worker, UI).
	python3 scripts/local-dev.py

setup: ## Install application dependencies from committed lockfiles.
	@set -e; for app in $(PYTHON_APPS); do uv sync --frozen --directory apps/$$app; done
	pnpm --dir apps/dashboard install --frozen-lockfile

install-skills: ## Install Codex/Claude Code entry-point skills for all workspaces.
	python3 scripts/install-agent-skills.py

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
DATABASE_URL ?= postgres://harnessflow:harnessflow@127.0.0.1:5432/harnessflow?sslmode=disable
API_MIGRATIONS := apps/api/migrations

proto: ## Regenerate proto + JSON-schema clients (Go, Python, TS). Idempotent.
	@echo ">> buf lint"
	buf lint
	@echo ">> buf generate (Go + Connect, Python, TypeScript)"
	buf generate
	perl -0777 -pi -e 's/\n+\z/\n/' packages/sdk/gen/ts/harnessflow/*/v1/*_pb.ts
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

demo: ## Run a bounded, explicit-mock legacy workflow smoke test.
	python3 scripts/local-dev.py --demo

eval: ## Run the eval suite against a workflow id (set HARNESSFLOW_WORKFLOW_ID).
	@test -n "$$HARNESSFLOW_WORKFLOW_ID" || { echo "set HARNESSFLOW_WORKFLOW_ID=<uuid>" >&2; exit 1; }
	uv run --directory apps/eval-runner harnessflow-eval --workflow-id $$HARNESSFLOW_WORKFLOW_ID --dataset $${HARNESSFLOW_DATASET:-research-assistant}

eval-gate: ## Run the CI eval-gate against locally changed workflow YAMLs (api+worker must be up).
	uv run --directory apps/eval-runner python $(CURDIR)/scripts/ci-eval-gate.py \
		--changed-files $$(git diff --name-only origin/main...HEAD -- 'packages/examples/workflows/*.yaml') \
		--out-md /tmp/eval-gate-comment.md

# --- Event firehose (ADR-0004) -----------------------------------------
events-consume: ## Drain the workflow-events topic to Parquet on MinIO (needs make up + an emitting worker).
	HARNESSFLOW_EVENTS_S3_ENDPOINT=http://localhost:9000 \
	AWS_ACCESS_KEY_ID=harnessflow AWS_SECRET_ACCESS_KEY=harnessflow \
	uv run --directory apps/event-consumer harnessflow-event-consumer

# --- Helm / kind --------------------------------------------------------
helm-sync-migrations: ## Re-vendor apps/api/migrations/*.up.sql into the chart's files/migrations/.
	rm -f infrastructure/helm/harnessflow/files/migrations/*.up.sql
	cp apps/api/migrations/*.up.sql infrastructure/helm/harnessflow/files/migrations/
	@echo "synced $$(ls apps/api/migrations/*.up.sql | wc -l | tr -d ' ') up-migrations into the chart"

helm-deps: ## Fetch upstream subchart tarballs (postgres/redis/temporal) into charts/.
	helm repo add bitnami  https://charts.bitnami.com/bitnami  --force-update
	helm repo add temporal https://go.temporal.io/helm-charts --force-update
	helm dependency build infrastructure/helm/harnessflow

helm-lint: ## helm lint the harnessflow chart.
	helm lint infrastructure/helm/harnessflow

helm-template: ## Render chart (bundled pg/redis, temporal off) — quick local diff.
	helm template hf infrastructure/helm/harnessflow \
		--set temporal.enabled=false --set externalTemporal.host=temporal.example

kind-up: ## Create the local kind cluster from infrastructure/kind/cluster.yaml.
	kind create cluster --name harnessflow --config infrastructure/kind/cluster.yaml

kind-down: ## Tear down the local kind cluster.
	kind delete cluster --name harnessflow

kind-load: ## Build the three first-party images and load them into kind.
	# api builds from the repo root (workspace dep on packages/sdk/gen/go).
	docker build -f apps/api/Dockerfile -t harnessflow/api:dev .
	docker build -t harnessflow/worker:dev    apps/worker
	docker build -t harnessflow/dashboard:dev apps/dashboard
	kind load docker-image --name harnessflow \
		harnessflow/api:dev harnessflow/worker:dev harnessflow/dashboard:dev

demo-bandit: ## (Week 13) A/B compare learned-retry vs static-retry policies.
	@echo "TODO(week-13): scripts/demo-bandit.sh"

test: ## Run launcher, Go, and Python unit tests (browser checks run separately in CI).
	python3 -m unittest discover -s scripts/tests -v
	python3 -m unittest discover -s apps/cli/tests -v
	cd Project-Documentation/projects/fixtures/expense-starter && python3 -m unittest discover -s tests -v
	cd Project-Documentation/projects/fixtures/ticket-starter && python3 -m unittest discover -s tests -v
	go test ./apps/api/...
	@set -e; for app in $(PYTHON_APPS); do uv run --frozen --directory apps/$$app pytest; done

lint: ## Run linters across all apps.
	uv run --frozen --directory apps/worker ruff check $(CURDIR)/scripts/local-dev.py $(CURDIR)/scripts/project-smoke.py $(CURDIR)/scripts/expense-acceptance.py $(CURDIR)/scripts/ticket-acceptance.py $(CURDIR)/scripts/tests
	uv run --frozen --directory apps/worker ruff format --check $(CURDIR)/scripts/local-dev.py $(CURDIR)/scripts/project-smoke.py $(CURDIR)/scripts/expense-acceptance.py $(CURDIR)/scripts/ticket-acceptance.py $(CURDIR)/scripts/tests
	uv run --frozen --directory apps/worker ruff check $(CURDIR)/Project-Documentation/projects/fixtures/expense-starter $(CURDIR)/Project-Documentation/projects/fixtures/ticket-starter
	uv run --frozen --directory apps/worker ruff format --check $(CURDIR)/Project-Documentation/projects/fixtures/expense-starter $(CURDIR)/Project-Documentation/projects/fixtures/ticket-starter
	uv run --frozen --directory apps/worker ruff check $(CURDIR)/scripts/install-agent-skills.py
	uv run --frozen --directory apps/worker ruff format --check $(CURDIR)/scripts/install-agent-skills.py
	uv run --frozen --directory apps/worker ruff check $(CURDIR)/apps/cli
	uv run --frozen --directory apps/worker ruff format --check $(CURDIR)/apps/cli
	cd apps/api && golangci-lint run
	@set -e; for app in $(PYTHON_APPS); do uv run --frozen --directory apps/$$app ruff check .; uv run --frozen --directory apps/$$app ruff format --check .; done
	cd apps/dashboard && ./node_modules/.bin/eslint

typecheck: ## Check Python and TypeScript types.
	uv run --frozen --directory apps/worker mypy harnessflow_worker
	uv run --frozen --directory apps/eval-runner mypy harnessflow_eval
	uv run --frozen --directory apps/event-consumer mypy harnessflow_events
	cd apps/dashboard && ./node_modules/.bin/tsc --noEmit

build: ## Build Go API and production dashboard.
	go build ./apps/api/...
	cd apps/dashboard && ./node_modules/.bin/next build

check: test lint typecheck build ## Run the full local quality gate.

fmt: ## Format code in-place across all apps.
	cd apps/api && golangci-lint fmt
	@set -e; for app in $(PYTHON_APPS); do uv run --frozen --directory apps/$$app ruff format .; done
	cd apps/dashboard && ./node_modules/.bin/eslint --fix

tools-check: ## Validate local harness tools, configuration, ports and Codex login.
	python3 scripts/local-dev.py --check

clean: ## Remove generated artifacts (does not touch source).
	@echo "TODO: clean build/test artifacts"
