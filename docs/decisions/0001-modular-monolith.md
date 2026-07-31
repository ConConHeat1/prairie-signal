# ADR 0001: Start with a modular monolith

- Status: Accepted
- Date: 2026-07-30

## Decision

Run one FastAPI application in Phase 0–1 while keeping source adapters, domain services,
repositories, API schemas, and scheduled jobs in separate modules and entry points.

## Rationale

The current product has one source and one region. Separate deployments would add failure modes
without improving scientific isolation. Module boundaries preserve later extraction paths.
