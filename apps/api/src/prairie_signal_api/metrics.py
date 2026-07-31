"""Low-cardinality service metrics.

No labels contain coordinates, query strings, URLs, station identifiers, alert
text, or other potentially location-bearing values.
"""

from prometheus_client import Counter, Gauge, Histogram

HTTP_REQUESTS = Counter(
    "prairie_signal_http_requests_total",
    "Completed API requests",
    ("method", "route", "status"),
)
HTTP_DURATION = Histogram(
    "prairie_signal_http_request_duration_seconds",
    "API request latency",
    ("method", "route"),
)
SOURCE_REQUESTS = Counter(
    "prairie_signal_source_requests_total",
    "Upstream source outcomes",
    ("source", "outcome"),
)
SOURCE_DURATION = Histogram(
    "prairie_signal_source_request_duration_seconds",
    "Upstream source latency",
    ("source",),
)
SOURCE_CIRCUIT_OPEN = Gauge(
    "prairie_signal_source_circuit_open",
    "Whether an upstream source circuit is open",
    ("source",),
)
STALE_FALLBACKS = Counter(
    "prairie_signal_stale_fallback_total",
    "Last-known-good fallbacks served",
    ("source",),
)
