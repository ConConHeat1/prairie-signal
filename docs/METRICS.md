# Metrics

## Exposed in Phase 1

- API request count, latency, and status by method and route template.
- NWS request outcomes, cache hits, conditional not-modified responses, failures, and latency.
- NWS circuit-open state and last-known-good fallback count.

Query strings, URLs, station identifiers, alert text, and exact coordinates are never metric
labels. Readiness and `/api/v1/sources` expose current configuration and source circuit health.

Before public deployment, add low-cardinality alert-feed age, observation-age, station-distance,
location-search outcome, and freshness-state metrics without adding location-bearing labels.

## Later forecast verification

- Radar: CSI, POD, FAR, FSS, structural and displacement errors at multiple thresholds and leads.
- Rain timing: arrival/end MAE, Brier score, accumulation error, misses, and false alerts.
- Standard weather: MAE, precipitation Brier score, quantitative precipitation error, interval
  coverage, and CRPS.
- Severe weather: precision-recall area, Brier score, reliability, CSI/POD/FAR, lead time,
  event-level detection, displacement, and stratification by event, season, and region.

Scores are compared with persistence, optical flow, official guidance where scientifically valid,
and previous model versions. Poor events remain visible.
