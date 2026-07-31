# Remaining Implementation Plan

- Last updated: 2026-07-31
- Overall status: In progress
- Current milestone: Milestone 2 — Observed radar system
- Current controlled slice: Slice 1 accepted; statewide Slice 2 is the next implementation target

This is the tracked execution plan for the continuation milestones. A milestone is not complete
merely because code exists. Completion requires passing automated checks, inspected output from a
representative live run, documented failure behavior, current source documentation, an acceptance
record, and a rollback path.

## Objective and claim boundary

Prairie Signal's first scientific objective is to beat persistence, constant-motion/optical-flow
extrapolation, and appropriate raw numerical guidance for zero-to-two-hour precipitation forecasts
across Nebraska. Lincoln remains the first accepted reference grid, but the public serving domain
now includes the entire state plus enough surrounding processing context for storms moving into
Nebraska. That is a target, not a current accuracy claim. No superiority claim may be published
until repeatable evaluation on unseen events supports it.

Official National Weather Service alerts remain authoritative and separate from observations,
numerical guidance, AI forecasts, and experimental severe-weather probabilities.

The detailed statewide coverage, hosting, graph, accuracy, and product sequence is tracked in
`docs/NEBRASKA_PRODUCT_ROADMAP.md`.

## Status legend

- `[x]` means evidence for that specific item is present in the repository.
- `[ ]` means incomplete, unverified, or awaiting recorded evidence.
- A checked child item does not complete its milestone automatically.

## Phase 0–1 audit status

### Phase 0 — Foundation: implemented in part; not formally accepted

Evidence present:

- [x] Monorepo boundaries for web, API, ingestion, shared packages, configuration, and
      infrastructure are documented in `docs/ARCHITECTURE.md`.
- [x] Docker Compose defines local web, API, PostgreSQL/PostGIS, Valkey, migration, optional
      ingestion, and optional observability services.
- [x] CI declares Python, web, contract, build, and browser-test jobs.
- [x] UTC, explicit-unit, privacy, immutable-provenance, cache/freshness, and official-versus-
      experimental decisions are recorded.
- [x] Alembic creates the Phase 1 persistence schema and append-only PostgreSQL safeguards.
- [x] The packaged Lincoln location resource is no longer hidden by the root runtime-data ignore
      rule.
- [x] The documented plural `ALERTS_*` freshness variables are consumed, with legacy singular
      aliases retained for compatibility.
- [x] Phase 1 frontend regressions found during this audit are covered: stale location results are
      cancelled, reduced-motion scrolling is respected, and mobile daily precipitation/wind values
      remain visible.

Acceptance gaps:

- [ ] Record a clean, sequential run of every declared lint, type-check, test, contract, build, and
      browser check.
- [ ] Add a real whole-stack integration smoke test; current browser tests mock the API boundary.
- [ ] Exercise PostgreSQL-specific archive triggers in integration tests rather than only applying
      the migration and testing portable models with SQLite.
- [ ] Complete a broader configuration audit beyond the alert-variable drift corrected in this
      slice and prove that every documented environment override is consumed.
- [ ] Add a Phase 0 acceptance report and recorded local demonstration.

### Phase 1 — Official weather: feature-complete in broad shape; not formally accepted

Evidence present:

- [x] Regional city, ZCTA, and coordinate search is implemented.
- [x] NWS current conditions, hourly forecasts, daily forecasts, and official alerts have versioned
      API contracts.
- [x] Fresh, delayed, stale, partial, and unavailable states are represented.
- [x] Conditional caching, bounded retries, circuit state, and last-known-good behavior have focused
      tests.
- [x] The frontend keeps official alert language distinct and exposes source/freshness information.
- [x] Scheduled long-term ingestion is restricted to configured public benchmark locations.

Acceptance gaps:

- [ ] Resolve the remaining Phase 0 acceptance gaps above.
- [ ] Record a live NWS smoke test using an identifying contact without storing credentials or user
      locations.
- [ ] Manually inspect current, hourly, daily, official-alert, stale, partial, and unavailable states.
- [ ] Record an end-to-end Compose demonstration and a Phase 1 acceptance report.
- [ ] Confirm documentation and generated OpenAPI/client contracts match the demonstrated runtime.
- [ ] Expand and accept location search, NWS grid/station selection, and time-zone behavior for all
      Nebraska locations rather than only the initial Lincoln-centered region.

Phase 0 and Phase 1 must not be retroactively labeled complete until those gaps are closed or an
acceptance report documents an explicitly approved exception.

## Gates that apply to every remaining milestone

- [ ] Source contracts are reverified against current official documentation and recorded under
      `docs/data-sources/` with a verification date.
- [ ] Raw files are immutable; derived products are versioned, restartable, idempotent, and written
      atomically.
- [ ] Missing, no-coverage, range-folded, corrupt, delayed, and stale inputs remain distinguishable;
      missing precipitation or reflectivity is never converted to zero.
- [ ] Observation, forecast initialization, valid, download, processing, publication, expiration,
      and displayed-local times are distinct where applicable.
- [ ] Every product records source, product, variable, units, grid/projection, bounds, horizontal
      resolution, timestamps, data age, processing version, quality flags, missing mask, and model
      version when applicable.
- [ ] Unit, integration, failure-path, and regression tests pass sequentially in the supported
      environment.
- [ ] A representative output is manually inspected and the evidence is recorded.
- [ ] Documentation, runnable demonstration, acceptance record, and rollback path are current.
- [ ] Official alerts and experimental guidance remain semantically and visually separate.

## Current session scope: Milestone 2, Slice 1

### Included

- [x] Record the verified MRMS source contract in `docs/data-sources/mrms.md`.
- [x] Discover timestamped `MergedReflectivityQCComposite_00.50` objects from the anonymous NOAA
      MRMS NODD bucket without using a mutable `latest` object as scientific identity.
- [x] Download only the selected object with bounded retry, bounded size, temporary-file cleanup,
      and a locally computed SHA-256 digest.
- [x] Preserve an immutable raw gzip/GRIB2 object and acquisition provenance.
- [x] Validate gzip and GRIB2 structure, product identity, valid time, grid, units, and expected
      missing/no-coverage codes.
- [x] Decode reflectivity without converting `-99` missing or `-999` no-coverage values to zero.
- [x] Crop the source to the configured Lincoln region and reproject it onto the versioned project
      grid while carrying a missing-data mask and quality flags.
- [x] Write normalized, chunked Zarr data and complete metadata atomically under a processing-version
      namespace.
- [x] Make repeat processing of the same source checksum and processing version idempotent.
- [x] Add focused fixture tests and one opt-in live smoke path.
- [x] Complete `docs/acceptance/MILESTONE_2_SLICE_1.md` with passing commands and inspected output.

### Explicitly excluded from Slice 1

- Precipitation-rate ingestion and every additional MRMS product
- Browser tiles, public radar API routes, animation, and frontend map controls
- Continuous scheduling or large historical backfills
- Nowcasting, AI training/inference, rain-arrival estimates, and accuracy claims
- Storm-object or experimental severe-weather guidance
- Production deployment

### Slice 1 promotion gate

Slice 1 was accepted on 2026-07-31 with the concrete evidence in
`docs/acceptance/MILESTONE_2_SLICE_1.md`. This does not complete Milestone 2.

### Exact next slice after Slice 1 acceptance

Milestone 2, Slice 2 is one observed frame from normalized Zarr to a deterministic statewide
Nebraska browser raster:

1. Add a versioned `nebraska-statewide-v1` processing/display grid in `EPSG:5070`, using the state
   as the serving area and a 200 km context buffer for incoming storms. Retain Lincoln as a
   regression grid.
2. Generate versioned tiles for one reflectivity frame with a documented dBZ color scale and a
   transparent, separately preserved no-data mask.
3. Add read-only observed-radar frame metadata and tile routes under the versioned API.
4. Display the one observed frame across Nebraska with state/county context, source time, age,
   product label, legend, and explicit unavailable/stale behavior.
5. Verify geographic alignment and visual values at western, central, and eastern Nebraska
   reference points against the same source frame manually.

Slice 2 will not add animation, prediction, precipitation rate, or continuous ingestion. Those are
separate later slices.

## Milestone checklist

### Milestone 2 — Observed radar system

- [x] Accept Slice 1: MRMS composite-reflectivity discovery through normalized Zarr.
- [ ] Accept Slice 2: one statewide Nebraska normalized observed frame through tiles, API, and
      inspected display.
- [ ] Add restartable scheduled ingestion, frame history, stale/failure behavior, and animation.
- [ ] Add precipitation rate only after the reflectivity path is reliable.
- [ ] Add further verified products incrementally rather than as one bulk adapter.
- [ ] Complete the full Milestone 2 acceptance report and rollback exercise.

### Milestone 3 — Historical weather-data pipeline

- [ ] Verify and document each historical source before acquisition.
- [ ] Build immutable raw, normalized, aligned, and leakage-safe training layers.
- [ ] Create the development dataset, event catalog, availability-time alignment, and quality reports.
- [ ] Demonstrate restartable/idempotent backfill and complete acceptance evidence.

### Milestone 4 — Nowcasting baselines

- [ ] Implement persistence, constant-motion, and optical-flow baselines.
- [ ] Archive every baseline forecast with initialization and valid times.
- [ ] Evaluate by threshold, lead, event, season, and geography with reproducible splits.
- [ ] Publish the baseline acceptance report before training a promoted AI model.

### Milestone 5 — Rain-arrival engine

- [ ] Produce probabilistic arrival, ending, duration, and accumulation outputs from verified inputs.
- [ ] Calibrate against held-out events and expose uncertainty and unavailable states.
- [ ] Inspect UI language so probabilities are not presented as certainty.
- [ ] Complete acceptance and rollback evidence.

### Milestone 6 — Initial AI predicted-radar model

- [ ] Build leakage-safe dataset splits and a reproducible first spatiotemporal model.
- [ ] Track data, code, configuration, checkpoints, metrics, and model lineage in a registry.
- [ ] Beat declared baselines on unseen evaluation data at the promotion gate.
- [ ] Keep output labeled as AI forecast radar and complete safety/acceptance review.

### Milestone 7 — Multimodal predicted radar

- [ ] Add HRRR, satellite, and lightning features one experiment at a time.
- [ ] Measure incremental value and operational availability for each modality.
- [ ] Produce calibrated probabilistic output with graceful missing-modality behavior.
- [ ] Complete promotion, acceptance, and rollback evidence.

### Milestone 8 — AI-corrected hourly weather forecasts

- [ ] Establish raw-guidance and official-guidance baselines.
- [ ] Train leakage-safe local corrections with calibrated quantiles/uncertainty.
- [ ] Blend and display corrections without misrepresenting official forecasts.
- [ ] Complete held-out verification and acceptance evidence.

### Milestone 9 — Storm-object identification and tracking

- [ ] Define and validate detection, association, split/merge, and lifecycle behavior.
- [ ] Archive versioned storm objects with observation and forecast provenance.
- [ ] Quantify tracking failures and geographic displacement.
- [ ] Complete acceptance and rollback evidence.

### Milestone 10 — Hail and damaging-wind models

- [ ] Audit label availability, reporting bias, and leakage risk.
- [ ] Establish calibrated hail and damaging-wind baselines before complex models.
- [ ] Evaluate precision-recall, reliability, lead time, and event/geography holdouts.
- [ ] Keep public output experimental and pass the severe-guidance safety gate.

### Milestone 11 — Tornado-threat model

- [ ] Approve rare-event labels, negative sampling, leakage controls, and target definition.
- [ ] Demonstrate calibration, precision-recall, misses, false alarms, and lead-time behavior on strict
      held-out data.
- [ ] Complete independent meteorological/product-safety review.
- [ ] Keep the model internal until every severe-guidance gate is satisfied.

### Milestone 12 — Verification and public transparency

- [ ] Archive every issued forecast before its valid time.
- [ ] Publish reproducible aggregate, event, seasonal, failure-case, and champion/challenger results.
- [ ] Prevent cherry-picking and keep historical model results visible.
- [ ] Complete public-verification acceptance evidence.

### Milestone 13 — Completed weather product interface

- [ ] Complete main, radar, storm, model-comparison, and verification experiences.
- [ ] Add accessible temperature/dew-point, precipitation, wind/gust, forecast-evolution,
      model-comparison, county-timeline, and public-verification graphs.
- [ ] Establish a Nebraska-specific visual identity without weakening official-alert prominence or
      scientific labels.
- [ ] Meet keyboard, screen-reader, contrast, motion, responsive, and failure-state requirements.
- [ ] Meet measured loading/rendering budgets on representative devices and networks.
- [ ] Complete cross-browser/manual acceptance evidence.

### Milestone 14 — Reliability and deployment

- [ ] Publish the scrubbed source repository and protect the promotion branch with required CI.
- [ ] Deploy a public beta without describing free-tier cold-start or scheduler behavior as
      guaranteed always-on service.
- [ ] Define development, staging, and production environments with immutable artifacts.
- [ ] Provision database, cache, object storage, tile delivery, secrets, backups, monitoring, and
      incident response.
- [ ] Test source outages, stale fallback, restore, rollback, cost controls, and capacity limits.
- [ ] Complete security review, container scanning, deployment acceptance, and rollback exercise.

### Milestone 15 — Notifications

- [ ] Implement official-alert notifications as a separate authoritative flow.
- [ ] Add calibrated rain notifications with clear opt-in, uncertainty, and quiet controls.
- [ ] Keep AI severe-weather notifications disabled until separately approved safety criteria exist.
- [ ] Complete delivery, duplication, expiry, privacy, failure, and rollback acceptance evidence.
