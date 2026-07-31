# ADR 0005: Official and experimental products cannot share semantics

- Status: Accepted
- Date: 2026-07-30

## Decision

Official NWS alert records are immutable domain objects. Experimental products use separate types,
routes, labels, colors, legends, and notification policies. Generated text cannot mutate official
meaning.

## Rationale

Technical separation makes the safety requirement testable and prevents future presentation code
from accidentally treating model output as public authority.
