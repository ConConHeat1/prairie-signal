# Deployment

Phase 0–1 is intentionally local-first. No external resources are provisioned by this milestone.

## Local profile

Docker Compose runs the web application, API, PostgreSQL/PostGIS, and Valkey. An optional
`observability` profile adds Prometheus and Grafana. Raw benchmark payloads and database state live
in named volumes and are not committed.

Before live NWS calls, copy `.env.example` to `.env` and set the blank NWS contact to a real public
URL or monitored email. Development fixtures and CI do not require live upstream access. Scheduled
benchmark archiving is enabled separately with the `live-ingestion` Compose profile.

## Production shape

A later deployment should provide:

- One HTTPS origin routing `/api/v1` to FastAPI and all other paths to Next.js.
- Managed PostgreSQL/PostGIS with backups and tested restore.
- A Redis-compatible cache with eviction and no durable user-location history.
- Object storage for immutable scientific payloads.
- Private service networking, secret management, WAF/rate limits, metrics, and alerting.
- A tile/object CDN before radar is exposed.

The frontend must never be published alone with fake data. Public deployment requires a budget,
service owner, approved product name/contact, backup policy, and incident path.

## Rollback

Application images are versioned immutably. Database migrations must be backward compatible for
one release. A rollback restores the prior images without deleting source archives or alert
revisions.
