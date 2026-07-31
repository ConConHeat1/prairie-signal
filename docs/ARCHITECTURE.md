# Architecture

## Phase 0–1 application topology

```text
Browser
  -> Next.js same-origin /api/v1 proxy
    -> FastAPI
      -> local Census location index
      -> NWS adapter
      -> Valkey hot cache and circuit state
      -> PostgreSQL/PostGIS metadata and official alert revisions
      -> immutable benchmark-source archive
```

Phase 1 is a modular monolith. Domain boundaries are explicit packages, not separately deployed
microservices. This keeps local operation understandable while preserving later extraction
points for ingestion, tile generation, inference, and verification.

The Phase 1 API and browser do not read or display radar artifacts.

## Milestone 2 Slice 1 scientific topology

```text
Operator: make ingest-radar
  -> opt-in Compose `radar` profile and one-shot ingestion CLI
    -> anonymous NOAA MRMS S3 discovery and bounded download
      -> immutable timestamped gzip/GRIB2 under /data/raw/mrms
        -> GRIB2 contract validation, sentinel masking, crop, and reprojection
          -> atomically published, versioned regional Zarr under /data/normalized/mrms
          -> diagnostic PNG and complete metadata.json beside the Zarr arrays
          -> append-only radar_artifacts provenance row in PostgreSQL
```

This path handles one current observed
`MergedReflectivityQCComposite_00.50` frame. It is deliberately disconnected from public FastAPI
routes and the Next.js application. There are no tile, map, animation, scheduling, historical
backfill, nowcast, or AI inference consumers in Slice 1.

## Repository boundaries

- `apps/web`: presentation, local-time formatting, accessibility, and device-local unit choice.
- `apps/api`: versioned HTTP contracts, orchestration, repositories, health, metrics, and security.
- `services/ingestion`: replaceable external-source adapters, benchmark jobs, and the opt-in MRMS
  acquisition/normalization command.
- `packages/api-client`: generated TypeScript API contracts and typed request helpers.
- `packages/weather-units`: presentation conversions with explicit source units.
- `packages/ui`: reusable presentational components.
- `configs`: versioned service-region and pipeline settings.
- `infrastructure`: local containers and monitoring configuration.

## Phase 1 request data flow

1. Validate and region-check a search or coordinate.
2. Resolve the NWS grid and candidate observation stations.
3. Read a fresh conditional cache entry when possible.
4. Fetch with a unique User-Agent, bounded timeout, conditional headers, and retry policy.
5. Normalize timestamps to UTC and quantities to their declared source units.
6. Attach freshness and quality metadata.
7. Return through the versioned API; convert time zone and unit presentation in the client.
8. For configured benchmark jobs only, archive a content-addressed raw payload and provenance
   record without overwriting previous revisions.

## Observed-MRMS normalization flow

1. Load and strictly validate the versioned MRMS source contract and Lincoln regional-grid
   configuration.
2. List only the current and previous UTC day beneath the fixed NOAA bucket/product prefix; parse
   canonical timestamped keys and select the newest non-future object.
3. Refuse a latest object older than the configured 15-minute current-data threshold.
4. Download with bounded retries, timeouts, compressed/decompressed size limits, and temporary-file
   cleanup; validate gzip and GRIB2 framing and compute SHA-256 for both forms.
5. Atomically preserve the original compressed object under:

   ```text
   /data/raw/mrms/{product}/YYYY/MM/DD/{source filename}
   ```

6. Decode exactly one geographic reflectivity band, verify product, UTC valid time, dBZ units, and
   `0.01`-degree source spacing, then keep `-99` missing and `-999` no-coverage states distinct from
   numeric reflectivity.
7. Crop with a source margin and reproject by nearest neighbor onto the configured 512 by 512,
   1,000-meter `EPSG:5070` Lincoln grid.
8. Publish the derived directory atomically under:

   ```text
   /data/normalized/mrms/{region}/{product}/{processing-version}/
     YYYY/MM/DD/YYYYMMDDTHHMMSSZ.zarr/
   ```

9. Record source identity, hashes, paths, grids, bounds, times, statistics, masks, quality flags,
   and processing version in an append-only PostgreSQL row. An exact rerun reuses matching raw and
   normalized artifacts; conflicting identity fails instead of overwriting evidence.

The default Docker volume is named `weather-data`; the `/data` paths above are paths inside the
ingestion container. `make ingest-radar` invokes only this one-shot profile. It does not require an
NWS contact or start the browser, API, cache, or recurring ingestion worker.

## Scientific storage levels

```text
raw source files
  -> normalized source data
    -> aligned ML grids
      -> lazily constructed training examples
        -> model predictions
          -> browser-sized tiles
```

Each level has a source checksum, acquisition time, valid time, projection, units, missing-value
definition, quality flags, and pipeline version. User-triggered requests do not create permanent
location history.

Slice 1 implements only the first `raw source files -> normalized source data` transition for one
observed MRMS reflectivity product. Aligned training grids, training examples, predictions, and
browser tiles remain future work. A diagnostic PNG is an inspection aid, not a public map tile.

## Availability

FastAPI reports liveness separately from dependency readiness. Each upstream source has its own
cache, conditional-request metadata, error counters, and circuit state. Last-known-good values are
returned only with explicit delayed or stale status. An unavailable alerts feed never becomes an
empty “no alerts” claim.

The opt-in MRMS command fails closed when discovery, integrity, product, time, unit, grid, or
publication checks fail. It does not substitute a clear frame for missing radar and does not affect
Phase 1 API availability. Source details and outstanding evidence are tracked in the
[MRMS dossier](data-sources/mrms.md), [remaining plan](REMAINING_IMPLEMENTATION_PLAN.md), and
[Slice 1 acceptance record](acceptance/MILESTONE_2_SLICE_1.md).
