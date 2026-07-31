# Privacy and Security

- No advertising, behavioral analytics, third-party tracking, or sale of location data.
- No accounts in Phase 1.
- Unit preference may use device-local storage. Selected location may be held for the current
  browser session but is not authoritative product data.
- Search strings, exact coordinates, raw URLs, request bodies, IP/location pairs, and User-Agent
  strings are excluded from application logs and metric labels.
- Interactive coordinates may be stored only in a short-lived cache. Durable benchmark ingestion
  uses predefined public locations and is not linked to users.
- External inputs have length, type, coordinate, region, response-size, and content-type limits.
- Official alert content is rendered as text, never injected as trusted HTML.
- Runtime secrets come from environment variables and are never committed.
- Downloaded data are treated as data, never executed or deserialized with pickle.
- Production model artifacts must be versioned, checksummed, signed, and loaded from an approved
  format.
- Dependency and container scans run before release. Security headers are enabled locally; a
  reviewed edge rate-limit policy is required before any public deployment.
