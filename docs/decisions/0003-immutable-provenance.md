# ADR 0003: Archive only configured benchmark sources immutably

- Status: Accepted
- Date: 2026-07-30

## Decision

Content-address every distinct raw payload collected by scheduled benchmark jobs and store its
checksum and timestamps in PostgreSQL. Never overwrite raw data. Do not durably archive arbitrary
interactive user coordinates.

## Rationale

Verification needs forecast revisions that cannot be reconstructed later, while privacy rules
forbid turning product use into permanent location history.
