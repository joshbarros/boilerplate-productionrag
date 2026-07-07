FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml uv.lock ./
COPY src/ src/

# Install dependencies
RUN uv sync --frozen --no-dev

# Expose ports
EXPOSE 8800 8801

# Default command (overridden by compose)
CMD ["uv", "run", "uvicorn", "ragcore.api:app", "--host", "0.0.0.0", "--port", "8800"]
