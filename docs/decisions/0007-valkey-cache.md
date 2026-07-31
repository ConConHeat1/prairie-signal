# ADR 0007: Use Valkey as the Redis-compatible cache

- Status: Accepted
- Date: 2026-07-30

## Decision

Use Valkey through the standard Redis protocol for transient response caching, conditional-request
metadata, rate-limit counters, and circuit state. PostgreSQL remains the durable relational store.

## Rationale

Valkey provides the required Redis-compatible behavior under an open-source license and can be
replaced behind the cache interface.
