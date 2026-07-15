FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Core package lives under packages/core in the monorepo
COPY packages/core/pyproject.toml packages/core/uv.lock ./
COPY packages/core/src/ src/
COPY packages/core/alembic/ alembic/
COPY packages/core/alembic.ini ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose ports
EXPOSE 8800 8801

# Default command (overridden by compose)
CMD ["uv", "run", "uvicorn", "ragcore.api.app:app", "--host", "0.0.0.0", "--port", "8800"]
