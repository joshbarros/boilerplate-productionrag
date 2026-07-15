# Production RAG — monorepo Makefile
# Core lives in packages/core; web UI in apps/web.

.PHONY: help install dev api web test lint eval eval-gate eval-matrix build clean migrate up down obs

CORE := packages/core
WEB := apps/web

help:
	@echo "Production RAG — monorepo"
	@echo ""
	@echo "  make install  — install Python (uv) + web (pnpm) deps"
	@echo "  make dev      — run core API (:8800) + web (:3000)"
	@echo "  make api      — core FastAPI only"
	@echo "  make web      — Next.js only"
	@echo "  make test     — core unit suite (no live network)"
	@echo "  make eval     — live OpenRouter eval (needs API key)"
	@echo "  make eval-gate — offline golden eval + regression gate (CI)"
	@echo "  make eval-matrix — offline config matrix (chunk×retrieval×rerank×backend)"
	@echo "  make migrate  — alembic upgrade head (needs Postgres)"
	@echo "  make up/down  — full compose (Postgres, Qdrant, OTel, Grafana :3001)"
	@echo "  make obs      — print observability endpoints"
	@echo "  make lint     — ruff + tsc"
	@echo "  make build    — production build of the web app"
	@echo "  make clean    — wipe build artifacts"

install:
	cd $(CORE) && uv sync --extra dev
	cd $(WEB) && pnpm install

dev:
	@echo "Starting core on :8800 and web on :3000…"
	@trap 'kill 0' EXIT; \
	(cd $(CORE) && API_TOKEN=$${API_TOKEN:-changeme} uv run uvicorn ragcore.api.app:app --host 127.0.0.1 --port 8800) & \
	(cd $(WEB) && NEXT_PUBLIC_API_TOKEN=$${API_TOKEN:-changeme} pnpm dev) & \
	wait

api:
	cd $(CORE) && API_TOKEN=$${API_TOKEN:-changeme} uv run uvicorn ragcore.api.app:app --host 127.0.0.1 --port 8800

web:
	cd $(WEB) && NEXT_PUBLIC_API_TOKEN=$${API_TOKEN:-changeme} pnpm dev

test:
	cd $(CORE) && uv run pytest --ignore=tests/e2e_test.py --ignore=tests/test_phase5_ingestion.py -q

eval:
	cd $(CORE) && EVAL_TEST=1 uv run pytest tests/test_phase7_evals.py::test_phase7_live_eval_suite -v -s

# Deterministic offline eval gate (no network / no API keys)
eval-gate:
	cd $(CORE) && uv run python -m ragcore.evals \
		--golden tests/fixtures/golden_set.json \
		--fixture tests/fixtures/langchain_demo.pdf \
		--mode offline --gate \
		--baseline evals/results/baseline_core_offline.json \
		--min-pass-rate 0.70 \
		--max-drop-pts 2.0 \
		--out evals/results/latest_core_offline.json \
		--md-out evals/results/latest_core_offline.md
	cd $(CORE) && uv run python -m ragcore.evals \
		--golden tests/fixtures/golden_regulatory.json \
		--fixture tests/fixtures/corpus/reg_bacen_circular.md \
		--fixture tests/fixtures/corpus/reg_cvm_instrucao.md \
		--fixture tests/fixtures/corpus/reg_lgpd.md \
		--fixture tests/fixtures/corpus/reg_simples_nacional.md \
		--fixture tests/fixtures/corpus/reg_asc606_en.md \
		--fixture tests/fixtures/corpus/reg_asc842_en.md \
		--mode offline --gate \
		--baseline evals/results/baseline_regulatory_offline.json \
		--min-pass-rate 0.70 \
		--max-drop-pts 2.0 \
		--out evals/results/latest_regulatory_offline.json \
		--md-out evals/results/latest_regulatory_offline.md

eval-matrix:
	cd $(CORE) && RERANK_CROSS_ENCODER=false uv run python -m ragcore.evals \
		--golden tests/fixtures/golden_set.json \
		--fixture tests/fixtures/langchain_demo.pdf \
		--matrix \
		--out evals/results/matrix_core_offline.json \
		--md-out evals/results/matrix_core_offline.md

obs:
	@echo "Grafana     http://localhost:3001  (admin/admin)"
	@echo "Prometheus  http://localhost:9090"
	@echo "Tempo       http://localhost:3200"
	@echo "Qdrant      http://localhost:6333/dashboard"
	@echo "OTLP gRPC   localhost:4317"
	@echo "Enable app export: OTEL_ENABLED=true OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317"

migrate:
	cd $(CORE) && uv run alembic upgrade head

up:
	docker compose -f infra/docker-compose.yml up -d --build

down:
	docker compose -f infra/docker-compose.yml down

lint:
	cd $(CORE) && uv run ruff check src/ tests/
	cd $(WEB) && pnpm typecheck

build:
	cd $(WEB) && pnpm build

clean:
	rm -rf $(WEB)/.next $(WEB)/.turbo $(WEB)/node_modules/.cache
	rm -rf $(CORE)/.pytest_cache $(CORE)/.ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
