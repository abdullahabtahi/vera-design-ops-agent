FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install production dependencies only
RUN uv sync --frozen --no-dev

# Install Playwright Chromium (needed for live website screenshot capture)
RUN uv run playwright install --with-deps chromium

# Copy source
COPY . .

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# PORT env var is injected by Cloud Run; default to 8000
CMD uv run uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
