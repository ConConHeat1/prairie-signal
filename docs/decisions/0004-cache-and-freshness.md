# ADR 0004: Separate cache validity from meteorological freshness

- Status: Accepted
- Date: 2026-07-30

## Decision

Honor upstream cache validators and expiry independently from product-age thresholds. Responses
carry fresh, delayed, stale, or unavailable status based on source time. Last-known-good data are
never relabeled current.

## Rationale

An HTTP response can be cacheable while describing old weather, and an upstream outage must not
silently erase useful—but stale—information.
