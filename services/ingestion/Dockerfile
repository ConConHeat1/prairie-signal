# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:0.12.0 AS uv

FROM python:3.13.14-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /workspace
COPY --from=uv /uv /uvx /bin/
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libexpat1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY services/ingestion/pyproject.toml services/ingestion/pyproject.toml
RUN uv sync \
    --frozen \
    --package prairie-signal-ingestion \
    --no-dev \
    --no-install-workspace

COPY apps/api apps/api
COPY services/ingestion services/ingestion
RUN uv sync --frozen --package prairie-signal-ingestion --no-dev

WORKDIR /workspace/services/ingestion
ENTRYPOINT ["uv", "run", "--no-sync", "--package", "prairie-signal-ingestion", "prairie-signal-ingest"]
CMD ["--help"]
