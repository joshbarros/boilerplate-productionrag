# Production RAG — monorepo Makefile
# Run the whole stack: backend (FastAPI :8800) + web (Next.js :3000)

.PHONY: help install dev api web test lint eval build clean

help:
	@echo "Production RAG — monorepo"
	@echo ""
	@echo "  make install  — install pnpm + Python deps"
	@echo "  make dev      — run backend (8800) + web (3000) in parallel"
	@echo "  make api      — backend only"
	@echo "  make web      — web only"
	@echo "  make test     — backend unit suite (68 tests)"
	@echo "  make eval     — live OpenRouter eval (8 cases, needs API key)"
	@echo "  make lint     — ruff + tsc"
	@echo "  make build    — production build of the web app"
	@echo "  make clean    — wipe build artifacts"

install:
	cd apps/backend && uv sync --extra dev
	cd apps/web && pnpm install

dev:
	@echo "Starting backend on :8800 and web on :3000…"
	@echo "Set API_TOKEN, OPENROUTER_API_KEY, OPENAI_API_KEY in apps/backend/.env"
	@trap 'kill 0' EXIT; \
	(cd apps/backend && API_TOKEN=$${API_TOKEN:-changeme} ./.venv/bin/uvicorn ragcore.api.app:app --host 127.0.0.1 --port 8800) & \
	(cd apps/web && NEXT_PUBLIC_API_TOKEN=$${API_TOKEN:-changeme} pnpm dev) & \
	wait

api:
	cd apps/backend && API_TOKEN=$${API_TOKEN:-changeme} ./.venv/bin/uvicorn ragcore.api.app:app --host 127.0.0.1 --port 8800

web:
	cd apps/web && NEXT_PUBLIC_API_TOKEN=$${API_TOKEN:-changeme} pnpm dev

test:
	cd apps/backend && uv run pytest --ignore=tests/e2e_test.py --ignore=tests/test_phase5_ingestion.py -q

eval:
	cd apps/backend && EVAL_TEST=1 uv run pytest tests/test_phase7_evals.py::test_phase7_live_eval_suite -v -s

lint:
	cd apps/backend && uv run ruff check src/ tests/
	cd apps/web && pnpm typecheck

build:
	cd apps/web && pnpm build

clean:
	rm -rf apps/web/.next apps/web/.turbo apps/web/node_modules/.cache
	rm -rf apps/backend/.pytest_cache apps/backend/.ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
