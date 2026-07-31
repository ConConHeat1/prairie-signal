# ADR 0002: Search a local Census index

- Status: Accepted
- Date: 2026-07-30

## Decision

Import Census Places and ZCTAs into PostGIS, filter results to the configured region, and parse
coordinates locally. Rank exact ZIP, exact name/state, prefix, then trigram matches.

## Rationale

This supports city, ZIP approximation, and coordinate search without sharing queries with a
third-party geocoder or depending on a commercial API. Street-address search is excluded.
