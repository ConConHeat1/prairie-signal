# Milestone 2 Slice 1 Acceptance Record

- Slice: MRMS quality-controlled composite reflectivity, discovery through normalized Zarr
- Product: `MergedReflectivityQCComposite_00.50`
- Region: configured Lincoln and central Great Plains grid
- Status: Accepted
- Opened: 2026-07-31
- Closed: 2026-07-31
- Acceptance decision: Accepted for `mrms-reflectivity-v1`

Milestone 2 is not complete: this acceptance covers only the first controlled vertical segment of
the observed-radar milestone. It is evidence for acquisition through normalized scientific storage,
not for a public radar product or prediction accuracy.

## Scope

Included:

- Timestamped anonymous S3 discovery
- One bounded MRMS gzip/GRIB2 acquisition path
- Immutable raw source storage and provenance
- Integrity and source-contract validation
- Decode, sentinel masking, regional crop, and reprojection
- Versioned normalized Zarr publication
- Restart/idempotency and focused automated tests
- One opt-in live sample and manual scientific inspection

Excluded:

- Precipitation rate or other MRMS products
- Browser tiles, radar API, animation, or frontend map
- Continuous scheduling and historical backfill
- Prediction, AI, rain-arrival, storm tracking, and severe guidance
- Production deployment

## Required acceptance criteria

### Source contract

- [x] `docs/data-sources/mrms.md` records the source contract and verification date.
- [x] A runtime listing confirms the documented product prefix and captures a representative key.
- [x] Any discrepancy with the source dossier is resolved and documented before processing.

### Discovery and acquisition

- [x] Discovery selects timestamped keys and never uses `latest` as immutable identity.
- [x] Product, domain, date, and filename are parsed without accepting path traversal or an
      arbitrary host/bucket.
- [x] Download uses bounded timeout, retry/backoff, response/object-size limits, and temporary files.
- [x] Interrupted or invalid downloads leave no promoted partial raw or normalized object.
- [x] The original gzip/GRIB2 bytes are stored immutably with locally computed SHA-256.
- [x] Object key, bucket, size, ETag/last-modified when present, discovery time, download time, and
      processing version are recorded.

### Decode and validation

- [x] Gzip corruption and truncated/non-GRIB input fail closed with a safe, actionable error.
- [x] Decoded product identity is `MergedReflectivityQCComposite_00.50`.
- [x] Filename UTC time and decoded valid time agree within the explicitly documented rule.
- [x] Native units are validated as dBZ.
- [x] Grid dimensions, coordinates, scanning order, extent, and spacing are validated.
- [x] Native `-99` missing cells and `-999` no-coverage cells remain distinct from numeric echoes.
- [x] Unexpected sentinel, unit, grid, product, or timestamp changes prevent promotion.

### Crop, reprojection, and normalized Zarr

- [x] The configured region/grid is loaded from a validated runtime configuration source.
- [x] The source is cropped with enough margin for safe reprojection.
- [x] Reprojection uses a documented, versioned method appropriate for reflectivity.
- [x] Missing and no-coverage masks survive crop and reprojection without becoming zero.
- [x] Output dimensions, coordinates, bounds, projection, and nominal resolution match the configured
      project grid.
- [x] Zarr contains reflectivity data, a missing/no-coverage mask or equivalent quality variables,
      and complete provenance.
- [x] Metadata includes source, product, variable, units, source grid, destination grid, bounds,
      resolution, valid time, discovery/download/processing times, data age, SHA-256, processing version,
      and quality flags.
- [x] Zarr publication is atomic; readers cannot observe a partially written product.
- [x] Reprocessing the same source checksum with the same processing version is idempotent.
- [x] A changed processing version can coexist without overwriting the earlier derived product.

### Automated verification

- [x] Unit tests cover key parsing, timestamp parsing, contract validation, and sentinel masking.
- [x] Unit tests cover corrupt gzip, truncated GRIB2, wrong product, wrong units, time mismatch, and
      unexpected grid.
- [x] A fixture integration test covers raw archive through normalized Zarr.
- [x] Tests assert expected destination shape, coordinates, representative dBZ values, and mask
      locations.
- [x] Tests prove repeat processing does not duplicate or rewrite the accepted product.
- [x] Tests prove temporary artifacts are removed after failure.
- [x] Python formatting passes.
- [x] Python linting passes.
- [x] Python type checking passes.
- [x] Relevant Python tests pass sequentially.
- [x] Migration/contract checks pass if this slice changes persistence or API contracts.

### Live and manual evidence

- [x] An opt-in live run successfully discovers and downloads one current timestamped NOAA object.
- [x] The exact live key, source valid time, discovery time, download completion time, observed
      latency, byte size, ETag/last-modified when present, and SHA-256 are recorded below.
- [x] The raw gzip and GRIB2 integrity checks pass for that object.
- [x] Source and normalized min/max/quantiles are inspected with masked sentinels excluded.
- [x] Counts of valid, missing, and no-coverage cells are recorded before and after reprojection.
- [x] A rendered diagnostic image is manually inspected for orientation, geographic placement,
      obvious seams/artifacts, and mask behavior.
- [x] At least three known geographic reference points are checked against source coordinates.
- [x] The live run is repeated and demonstrates idempotent no-op/reuse behavior.
- [x] A forced upstream failure demonstrates explicit failure without publishing a clear or partial
      radar product.
- [x] The reviewer signs the decision below only after inspecting the evidence.

## Command evidence

The final checks below ran from the repository root on 2026-07-31. The first unprivileged browser
run could not bind port 3000 (`EPERM`) in the execution sandbox; the identical approved local-server
rerun passed and is recorded here as the resolved result.

| Check                        | Exact command                                                                                                                                                                                                                                          | Result                                               | Date/time UTC        | Notes                                                                                                                                 |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| Format                       | `.venv/bin/ruff format --check apps services`                                                                                                                                                                                                          | Pass, 54 files formatted                             | 2026-07-31 14:27 UTC | Final rerun included all Python changes.                                                                                              |
| Lint                         | `.venv/bin/ruff check apps services`                                                                                                                                                                                                                   | Pass                                                 | 2026-07-31 14:27 UTC | No Ruff findings.                                                                                                                     |
| Type check                   | `.venv/bin/mypy --cache-dir /tmp/prairie-signal-mypy-cache apps/api services/ingestion`                                                                                                                                                                | Pass, 34 source files                                | 2026-07-31 14:28 UTC | Strict mode.                                                                                                                          |
| Focused unit tests           | `.venv/bin/pytest services/ingestion/tests/test_mrms_adapter.py services/ingestion/tests/test_mrms_processing.py services/ingestion/tests/test_radar_config.py services/ingestion/tests/test_radar_metadata.py apps/api/tests/test_radar_models.py -q` | Pass, 34 tests                                       | 2026-07-31 14:28 UTC | Includes transport, science contract, Zarr, metadata, and migrations.                                                                 |
| Fixture integration          | `.venv/bin/pytest services/ingestion/tests/test_mrms_processing.py -q`                                                                                                                                                                                 | Pass, 8 tests                                        | 2026-07-31 14:28 UTC | Includes raw fixture through Zarr and forced write interruption.                                                                      |
| Full relevant Python tests   | `.venv/bin/pytest -q`                                                                                                                                                                                                                                  | Pass, 88 tests                                       | 2026-07-31 14:28 UTC | One upstream `TestClient` deprecation warning; no test failure.                                                                       |
| Coverage regression          | `.venv/bin/pytest --cov=apps/api --cov=services/ingestion --cov-report=term -W error::ResourceWarning -q`                                                                                                                                              | Pass, 88 tests, 86% total coverage                   | 2026-07-31 14:48 UTC | No resource leak warning; one upstream `TestClient` deprecation warning.                                                              |
| Migration/DB                 | `DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:5432/prairie_signal .venv/bin/alembic -c apps/api/alembic.ini upgrade head`                                                                                                                           | Pass, head `20260731_0003`                           | 2026-07-31 14:21 UTC | Additive provenance migration preserved the existing row.                                                                             |
| Alembic drift                | `DATABASE_URL=postgresql+asyncpg://...@127.0.0.1:5432/prairie_signal .venv/bin/alembic -c apps/api/alembic.ini check`                                                                                                                                  | Pass, no new upgrade operations                      | 2026-07-31 14:50 UTC | Reflection is scoped away from PostGIS-owned topology/TIGER tables.                                                                   |
| PostgreSQL immutability      | `docker-compose exec -T db psql ... -c "UPDATE radar_artifacts SET source = source WHERE id = 'e779af13-...';"`                                                                                                                                        | Expected rejection: `radar_artifacts is append-only` | 2026-07-31 14:41 UTC | No row was modified.                                                                                                                  |
| Web regression               | `pnpm format:check`; `pnpm lint`; `pnpm typecheck`; `pnpm test`; `pnpm build`; `pnpm api:check`                                                                                                                                                        | Pass; 16 tests and production build                  | 2026-07-31 14:14 UTC | Confirms the backend-only slice did not regress Phase 1 web/contracts.                                                                |
| Browser regression           | `pnpm test:e2e`                                                                                                                                                                                                                                        | Pass, 8 tests                                        | 2026-07-31 14:17 UTC | Approved rerun allowed Playwright's local test server to bind.                                                                        |
| Dependency security          | `.venv/bin/pip-audit`; `pnpm audit --prod`                                                                                                                                                                                                             | Pass, no known vulnerabilities                       | 2026-07-31 14:46 UTC | Local workspace packages are not published on PyPI and were correctly skipped by name.                                                |
| Compose contract             | `docker-compose config -q`; `docker-compose --profile radar config --services`                                                                                                                                                                         | Pass                                                 | 2026-07-31 14:29 UTC | Radar remains opt-in.                                                                                                                 |
| Container runtime            | `docker-compose --profile radar build mrms-ingestion`; `docker-compose --profile radar run --rm --no-deps mrms-ingestion`                                                                                                                              | Pass                                                 | 2026-07-31 14:52 UTC | First run exposed missing `libexpat.so.1`; `libexpat1` was added and the final rebuilt image processed live frame `20260731T145041Z`. |
| Live smoke                   | `DATABASE_URL=... DATA_DIRECTORY=data REGION_CONFIG_PATH=configs/regions/lincoln-512km.yaml MRMS_SOURCE_CONFIG_PATH=configs/sources/mrms.yaml uv run --offline --no-sync --package prairie-signal-ingestion prairie-signal-ingest --mrms-latest`       | Pass                                                 | 2026-07-31 14:24 UTC | Anonymous public NOAA read; exact evidence below.                                                                                     |
| Idempotent rerun             | Same live-smoke command                                                                                                                                                                                                                                | Pass, `reused: true`, same UUID/path/hashes          | 2026-07-31 14:25 UTC | Database query confirmed exactly one row for the source key.                                                                          |
| Forced-failure demonstration | `.venv/bin/pytest services/ingestion/tests/test_mrms_adapter.py::test_discovery_outage_has_bounded_retries_and_explicit_failure -q`                                                                                                                    | Pass                                                 | 2026-07-31           | Three bounded attempts, explicit error, no publication.                                                                               |

## Live-source evidence

- S3 bucket: `noaa-mrms-pds`
- Object key:
  `CONUS/MergedReflectivityQCComposite_00.50/20260731/MRMS_MergedReflectivityQCComposite_00.50_20260731-142241.grib2.gz`
- Product: `MergedReflectivityQCComposite_00.50`
- Filename time UTC: `2026-07-31T14:22:41Z`
- Decoded valid time UTC: `2026-07-31T14:22:41Z` (exact agreement)
- Discovered at UTC: `2026-07-31T14:24:35.970489Z`
- Download completed at UTC: `2026-07-31T14:24:36.154804Z`
- Observed valid-to-download latency: `115.154804` seconds
- Byte size: `993861` bytes compressed; `1047179` bytes decoded GRIB2
- ETag: `4e39134463b0892df70056623a5806b4`
- Last modified: `2026-07-31T14:23:26Z`
- Compressed SHA-256: `3fad0d3d473383ead3c8d3d0efe22ae35e54157bea734f31f1ebb8cb3b622462`
- Decoded GRIB2 SHA-256:
  `9828cfd82bad90876429050eadf5940ed59d7a5753dcf3631b2042ee78fb1192`
- Source grid dimensions/extent: `7000 x 3500`, west/east `-130/-60`, south/north
  `20/55` degrees within decoder tolerance, west-to-east and north-to-south scanning, approximately
  `0.01` degree spacing. The complete decoded GRIB CRS/WKT is retained rather than mislabeled as
  EPSG:4326.
- Destination grid dimensions/extent: `512 x 512`, `EPSG:5070`, 1,000 m; projected bounds
  `[-314781.5092, 1722334.7404, 197218.4908, 2234334.7404]`; geographic bounds west
  `-99.885584`, south `38.477093`, east `-93.564760`, north `43.104067`.
- Processing version: `mrms-reflectivity-v1`, nearest-neighbor mask-aware reprojection
- Database identity: `e779af13-476e-4a53-b912-52f85a7f592f`
- Normalized Zarr location/identity:
  `data/normalized/mrms/lincoln-512km/MergedReflectivityQCComposite_00.50/mrms-reflectivity-v1/2026/07/31/20260731T142241Z.zarr`

## Scientific inspection evidence

| Measurement                | Source grid          | Normalized grid      | Expected interpretation                                                      |
| -------------------------- | -------------------- | -------------------- | ---------------------------------------------------------------------------- |
| Valid-cell count           | 612                  | 388                  | Native column is the margin-expanded regional source crop, not all CONUS.    |
| Missing (`-99`) count      | 297,504              | 261,756              | Remained quality flag 1 and `NaN`, never zero.                               |
| No-coverage (`-999`) count | 0                    | 0                    | None occurred in this in-coverage crop; distinct behavior is fixture-tested. |
| Minimum valid dBZ          | 4.000015             | 4.000015             | No sentinel leakage.                                                         |
| Maximum valid dBZ          | 47.500015            | 41.500015            | Plausible nearest-grid sample change.                                        |
| Median valid dBZ           | 18.000015            | 17.500015            | Diagnostic only.                                                             |
| 5th/95th percentile dBZ    | 6.500015 / 36.500015 | 6.500015 / 32.000015 | Masked sentinels excluded.                                                   |

Diagnostic render:

- Artifact/path:
  `data/normalized/mrms/lincoln-512km/MergedReflectivityQCComposite_00.50/mrms-reflectivity-v1/2026/07/31/20260731T142241Z.zarr/diagnostic-preview.png`
- Color scale and range: fixed thresholds at 5, 10, 20, 30, 40, 50, 60, and 70 dBZ; missing is
  gray and no-coverage/outside-source is dark. The inspected frame's valid range was
  `4.000015..41.500015` dBZ.
- Orientation checked: Yes; target `x` increases eastward and `y` decreases southward.
- Geographic alignment checked: Yes. Lincoln mapped from native row/column `1418/3329` to target
  `255/255`; Omaha from `1374/3406` to `206/320`; Grand Island from `1407/3165` to `241/119`.
  Each reference point preserved the native missing classification in the target mask.
- Mask/no-coverage appearance checked: Yes. Sparse echoes were visible without full-frame seams;
  regional missing cells were gray and no numeric `-99` or `-999` leaked into reflectivity.
- Reviewer notes: The render is a diagnostic scientific artifact, not a basemap or public tile.
  Coordinate/mask checks establish orientation and reprojection consistency; they do not establish
  forecast skill or independent meteorological ground truth.

## Failure-mode evidence

| Failure                            | Required behavior                               | Evidence                                                                                                                                                         |
| ---------------------------------- | ----------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Bucket/list unavailable            | Bounded retry, then explicit unavailable result | Mock transport test verifies three attempts/backoff and `MRMSDiscoveryError`.                                                                                    |
| Object disappears between list/get | Safe retry/rediscovery; no partial promotion    | Download failure/partial-stream tests verify bounded explicit failure and empty temporary/raw promotion paths; a later one-shot run starts with discovery again. |
| Truncated/corrupt gzip             | Integrity error; temporary file removed         | Parameterized corrupt/truncated gzip tests pass.                                                                                                                 |
| Invalid/non-GRIB payload           | Decode error; no normalized output              | GRIB framing and decoder contract tests fail closed before publication.                                                                                          |
| Wrong product or units             | Contract-change failure                         | Strict key/product and decoded dBZ unit tests pass.                                                                                                              |
| Filename/GRIB time mismatch        | Contract-change failure                         | Five-minute mismatch fixture fails with no normalized directory.                                                                                                 |
| Unexpected grid                    | Contract-change failure                         | Resolution fixture plus live 7000 by 3500 extent/scan validation pass.                                                                                           |
| Unexpected sentinel                | Contract-change failure                         | Synthetic `-95` sentinel test fails with no publication.                                                                                                         |
| Zarr write interruption            | No reader-visible partial product               | Forced partial-chunk write raises; both `.zarr` and staging `.part` remain absent.                                                                               |
| Repeat identical input             | Idempotent reuse/no-op                          | Live rerun returned `reused: true`, the same UUID/path/hashes, and one DB row.                                                                                   |

## Rollback path

Rollback for Slice 1 is operational disablement, not deletion of scientific evidence:

1. Disable the MRMS Slice 1 command/job or feature configuration so no new objects are acquired.
2. Restore the prior application/service artifact and, if applicable, roll back only a backward-safe
   schema change according to its migration notes.
3. Mark affected normalized products inactive or unsupported by processing version; do not rewrite
   them in place.
4. Retain immutable raw source bytes, hashes, provenance, logs, and this acceptance evidence unless
   an explicitly authorized retention procedure requires otherwise.
5. Confirm Phase 1 NWS weather and official-alert paths remain operational and unaffected.
6. Open a corrective slice before re-enabling ingestion.

Rollback rehearsal:

- [x] The disable path is documented with the final command/configuration name.
- [x] The rollback is rehearsed without deleting raw source data.
- [x] Existing Phase 1 health/readiness behavior is verified after rollback.

Operational rollback evidence: default `docker-compose config --services` omitted
`mrms-ingestion`, while `docker-compose --profile radar config --services` included it. Therefore
omitting the profile disables the one-shot path without deleting the repository `data/` artifacts
or Docker `weather-data` volume. The already running Phase 1 API remained healthy and returned
`status: ok`; the web root returned HTTP 200. A destructive schema downgrade was intentionally not
used as an operational disable mechanism.

## Acceptance decision

- Decision: **Accepted for Milestone 2 Slice 1 only.**
- Accepted processing version: `mrms-reflectivity-v1`
- Reviewer: Codex implementation review (automated verification plus artifact inspection)
- Review date: 2026-07-31
- Exceptions: No Slice 1 exception. The full Python suite reports one third-party
  FastAPI/Starlette `TestClient` deprecation warning, which does not affect the ingestion runtime.
- Follow-up: Implement Milestone 2 Slice 2—one deterministic observed frame through versioned
  tiles, read-only API metadata, and an inspected browser display—without adding animation or
  prediction yet.
