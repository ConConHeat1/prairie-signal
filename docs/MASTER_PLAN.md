# Prairie Signal Master Plan

Prairie Signal is an ad-free, privacy-respecting weather platform built from public
meteorological data. Lincoln is the first accepted reference location and regression grid. The
public-service target is every location in Nebraska, with a versioned statewide serving domain and
enough surrounding processing context to observe and predict storms moving into the state.

## Product principles

1. Official National Weather Service products remain authoritative and visually dominant.
2. Experimental guidance is never described as a warning.
3. Missing or stale data are visible; missing values are never silently replaced with zero.
4. Every product carries source, valid-time, processing, quality, and version metadata.
5. Accuracy claims require repeatable verification against observations and strong baselines.
6. User searches and coordinates are not permanently stored or associated with identity.

## Delivery phases

### Phase 0 — Foundation

The monorepo, architecture boundaries, local runtime, CI, safety rules, provenance conventions,
configuration, and operational documentation.

### Phase 1 — Official weather

Regional location search, current NWS station observations, hourly and day/night forecasts,
official alerts, source freshness, resilient caching, and honest failure states. No machine
learning or radar is exposed by the Phase 1 API or web application.

### Phase 2 — Observed radar

MRMS ingestion, validation, statewide Nebraska reprojection with surrounding storm context, tiled
observed radar, lightning, official warning polygons, and desktop/mobile animation.

Current implementation status: Slice 1 code provides an opt-in, one-frame
`MergedReflectivityQCComposite_00.50` path from timestamped NOAA discovery through immutable raw
storage, validation, regional reprojection, versioned normalized Zarr, and append-only provenance.
Its acceptance record remains the authority for whether that slice is promoted. Public radar API
routes, tiles, maps, animation, recurring operation, additional radar products, and every
predictive feature remain incomplete.

### Phase 3 — Historical data

Immutable historical MRMS, HRRR/NBM, GOES, lightning, observations, storm events, event
catalogs, data-quality reports, and leakage-safe example generation.

### Phase 4 — Nowcast baselines

Persistence, constant translation, optical flow, probabilistic rain timing, and baseline
verification.

### Phase 5 — AI radar nowcast

A validated spatiotemporal model, probabilistic thresholds, ensembles, model registry, live
inference, and clearly labeled AI forecast tiles.

### Phase 6 — Point correction

Observation-targeted corrections to NBM, HRRR, and official guidance for temperature, dew point,
wind, gusts, and precipitation, including calibrated quantiles.

### Phase 7 — Experimental severe guidance

Hail, damaging-wind, rotation, tornado, and flash-flood research in that order. Public exposure
requires calibration, independent review, and the safety gate in `MODEL_SAFETY.md`.

### Phase 8 — Product completion

PWA support, optional device-local saved locations, official-alert notifications, verification
replay, storm details, statewide county experiences, accessible forecast/model/verification graphs,
a Nebraska-specific visual identity, accessibility hardening, and production optimization.

## Current controlled handoff

Slice 1 was accepted on 2026-07-31 in the
[Milestone 2 Slice 1 acceptance record](acceptance/MILESTONE_2_SLICE_1.md) without marking all of
Phase 2 complete. The next smallest implementation slice adds the versioned Nebraska domain and
moves one deterministic observed frame from normalized Zarr through versioned tiles, read-only API
metadata, and a manually inspected statewide browser display. That slice must retain source time,
age, product identity, legend, geographic alignment, and explicit stale/unavailable behavior.

Animation, continuous ingestion, precipitation-rate products, rain-arrival estimates, and AI
prediction are not part of that next slice. The detailed order, verification gates, and claim
boundaries live in the [remaining implementation plan](REMAINING_IMPLEMENTATION_PLAN.md), while
the verified input contract lives in the [MRMS source dossier](data-sources/mrms.md). The hosting,
statewide coverage, graph, and accuracy sequence is detailed in the
[Nebraska product roadmap](NEBRASKA_PRODUCT_ROADMAP.md).
