# ADR 0006: UTC and explicit units; local presentation only

- Status: Accepted
- Date: 2026-07-30

## Decision

Store and transmit ISO-8601 UTC instants and declared units. Convert to a location’s IANA time zone
and selected display units only at the presentation boundary. Strip location-bearing values from
logs and metrics.

## Rationale

This avoids daylight-saving ambiguity, hidden conversions, and accidental privacy leakage while
keeping unit behavior testable.
