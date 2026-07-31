# Prairie Signal

Prairie Signal is an ad-free, privacy-respecting weather platform for Lincoln, Nebraska and the
surrounding central Great Plains. Phase 1 presents real National Weather Service forecasts,
station observations, and official alerts with visible source age and failure states.

Milestone 2 Slice 1 adds an opt-in, backend-only path that acquires one current NOAA MRMS observed
composite-reflectivity frame and normalizes it for later scientific work. It does **not** expose
radar through the public API or web application and does not predict future radar. This repository
does not contain machine-learning forecasts, severe-weather scores, advertisements, tracking, or
user accounts.

## What works in Phase 1

- City, ZIP/ZCTA, and coordinate search within the configurable Lincoln-centered region.
- Current conditions from a valid nearby NWS observation station.
- Forty-eight-hour NWS forecast.
- NWS day/night forecast for every available period, normally about seven days.
- Official NWS alerts with the original meaning, metadata, and geometry preserved.
- US customary and metric presentation.
- Conditional caching, bounded retries, circuit breaking, last-known-good fallback, and explicit
  fresh, delayed, stale, partial, and unavailable states.
- Local PostGIS and Valkey services, immutable benchmark-source archiving, metrics, tests, and CI.

## Prerequisites

- Node.js 24 LTS
- pnpm 10.15.1 through Corepack
- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- Docker with Compose (Docker Desktop or Docker CLI plus Colima)

## First run

1. Create local configuration:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and replace `NWS_CONTACT` with a real public website or email. NWS requires an
   identifying User-Agent for live calls. If it remains blank, the stack still starts but weather
   endpoints clearly report that NWS is not configured.

3. Start the full stack:

   ```bash
   docker compose up --build
   ```

   If Compose is installed as the standalone Homebrew plugin, use `docker-compose up --build`.

4. Open:

   - Web: <http://localhost:3000>
   - API documentation: <http://localhost:8000/api/docs>
   - API metrics: <http://localhost:8000/metrics>

The default location is Lincoln, Nebraska. Stop the stack with `docker compose down`.

### Scheduled benchmark ingestion

Once `NWS_CONTACT` contains a real public contact, enable the immutable Lincoln benchmark archive
worker with:

```bash
docker compose --profile live-ingestion up --build
```

Keeping this worker behind a profile prevents an unconfigured development checkout from repeatedly
calling or retrying the NWS. Interactive searches and coordinates are never archived.

### Opt-in observed MRMS ingestion

The Milestone 2 Slice 1 job is a one-shot scientific ingestion command. It discovers the newest
timestamped `MergedReflectivityQCComposite_00.50` object in NOAA's anonymous public MRMS bucket,
rejects stale or source-contract-breaking input, preserves the original gzip/GRIB2 bytes, and
normalizes the configured Lincoln-region crop to versioned Zarr. Completed provenance is recorded
in the append-only `radar_artifacts` database table.

Run it independently of the Phase 1 API and web application with:

```bash
make ingest-radar
```

This requires Docker with Compose, outbound HTTPS access to the public NOAA bucket, and enough local
space for the `weather-data` Docker volume. Compose starts PostgreSQL and applies migrations before
the job. It does not require `NWS_CONTACT`. For standalone Compose, run:

```bash
make COMPOSE=docker-compose ingest-radar
```

The container reads `configs/sources/mrms.yaml` and `configs/regions/lincoln-512km.yaml`. Its
versioned outputs are stored at:

```text
/data/raw/mrms/MergedReflectivityQCComposite_00.50/YYYY/MM/DD/*.grib2.gz
/data/normalized/mrms/lincoln-512km/MergedReflectivityQCComposite_00.50/
  mrms-reflectivity-v1/YYYY/MM/DD/YYYYMMDDTHHMMSSZ.zarr/
```

Each Zarr directory includes reflectivity, explicit quality/missing/no-coverage arrays, coordinates,
provenance attributes, `metadata.json`, and a diagnostic preview used for inspection. These files
are pipeline artifacts, not a supported public radar product. The command processes one latest
frame and exits; scheduling, frame history, tiles, API routes, browser display, animation, and
prediction remain separate work.

See the [MRMS source dossier](docs/data-sources/mrms.md),
[remaining implementation plan](docs/REMAINING_IMPLEMENTATION_PLAN.md), and
[Slice 1 acceptance record](docs/acceptance/MILESTONE_2_SLICE_1.md) for the exact source contract,
recorded verification evidence, next gates, and claim boundaries.

The [Nebraska product and deployment roadmap](docs/NEBRASKA_PRODUCT_ROADMAP.md) records the planned
statewide domain, public-hosting stages, observed and predicted radar sequence, accuracy promotion
rules, accessible graphs, and Nebraska-specific product direction.

## Native development

Install locked dependencies:

```bash
corepack enable
pnpm install --frozen-lockfile
uv sync --all-packages --dev --frozen
```

Run the API:

```bash
DATABASE_URL=postgresql+asyncpg://prairie_signal:development-only-change-me@127.0.0.1:5432/prairie_signal \
CACHE_URL=redis://127.0.0.1:6379/0 \
uv run --package prairie-signal-api uvicorn prairie_signal_api.main:app --reload --no-access-log --port 8000
```

Run the web application in a second terminal:

```bash
API_INTERNAL_URL=http://localhost:8000 pnpm --filter @prairie-signal/web dev
```

## Verification

```bash
uv run ruff format --check apps services
uv run ruff check apps services
uv run mypy apps/api services/ingestion
uv run pytest
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
pnpm api:check
pnpm test:e2e
```

Tests use recorded NWS-shaped fixtures. Live NOAA smoke tests are opt-in so CI does not consume
public capacity or fail because of an upstream outage.

## Optional observability

```bash
docker compose --profile observability up --build
```

Prometheus is available at <http://localhost:9090> and Grafana at <http://localhost:3001>.
Development credentials come from `.env`.

## Data and privacy

The repository includes a small Lincoln-area Census-shaped index so development and CI work
offline. To build the complete current regional index from the official 2025 U.S. Census Places
and ZCTA Gazetteers, run:

```bash
docker compose --profile maintenance run --rm census-loader
docker compose restart api
```

Use `docker-compose` in those commands if Compose is installed as the standalone Homebrew plugin.
The loader verifies the pinned Census source checksums, archives the immutable source files,
filters records to 256 km from Lincoln (a 512 km-wide region), writes shared Places/ZCTA TSVs, and
upserts the local database. The API automatically reads those files after restart. A ZCTA is an
approximation of a postal ZIP. Weather and alerts come from the National Weather Service.

Application logs exclude search strings, exact coordinates, raw URLs, and IP/location pairs.
Interactive location requests use short-lived cache entries and are not written as user history.
Only predefined public benchmark locations are eligible for immutable source archiving.

## Known limitations

- Search is restricted to the configured 512 km Lincoln-centered region.
- Current conditions are from a nearby station, not a sensor at the selected point, and may be
  delayed upstream.
- NWS point forecasts normally cover about seven days; Prairie Signal does not invent a ten-day
  extension.
- Source confidence is shown as unavailable because NWS does not publish a confidence value in
  these responses.
- The Phase 1 API and web UI remain NWS-only. The opt-in MRMS pipeline produces internal observed
  data only; there is no public radar route, map, animation, or radar prediction.
- There is no rain-arrival estimate, AI summary, severe prediction, notification, saved location,
  or public deployment in this milestone.

See [the master plan](docs/MASTER_PLAN.md), [architecture](docs/ARCHITECTURE.md),
[data-source notes](docs/DATA_SOURCES.md), and [model-safety rules](docs/MODEL_SAFETY.md).
