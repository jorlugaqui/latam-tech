# syntax=docker/dockerfile:1

# ---- base: interpreter, uv, non-root user ---------------------------------------
FROM python:3.12.11-slim-bookworm AS base
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
RUN groupadd --system app && useradd --system --gid app --home-dir /app app
WORKDIR /app

# ---- runtime: production dependencies + application code ------------------------
FROM base AS runtime
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-dev
USER app
EXPOSE 8001
CMD ["uvicorn", "mock_tools.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]

# ---- dev: all dependency groups; source is bind-mounted at /app -------------------
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
ENV PYTHONPATH=/app/src
USER app
CMD ["pytest"]
