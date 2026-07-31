# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.0 AS uv

FROM python:3.13.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace
COPY --from=uv /uv /uvx /bin/
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY services/ingestion/pyproject.toml services/ingestion/pyproject.toml
RUN uv sync --frozen --package prairie-signal-api --no-dev --no-install-workspace

COPY apps/api apps/api
RUN uv sync --frozen --package prairie-signal-api --no-dev

WORKDIR /workspace/apps/api
EXPOSE 8000
CMD ["uv", "run", "--no-sync", "--package", "prairie-signal-api", "uvicorn", "prairie_signal_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
