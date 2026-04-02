"""
Prometheus metrics — Phase C.

Exposes counters, histograms, and gauges consumed by the /metrics endpoint.
Import individual metrics into scoring paths to instrument them.
"""

from prometheus_client import Counter, Histogram, Gauge, Info

# -- Scoring counters --

TRIPS_SCORED = Counter(
    "porter_trips_scored_total",
    "Total trips scored by the ML model",
    ["tier", "path"],   # path: stateless | pandas | stream
)

FRAUD_CASES_CREATED = Counter(
    "porter_fraud_cases_created_total",
    "Fraud cases persisted to the database",
    ["tier"],
)

# -- Latency --

SCORING_LATENCY = Histogram(
    "porter_scoring_latency_seconds",
    "End-to-end trip scoring latency in seconds",
    ["path"],
    buckets=[0.002, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
)

HTTP_REQUEST_LATENCY = Histogram(
    "porter_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# -- Stream health --

STREAM_LAG = Gauge(
    "porter_stream_lag_messages",
    "Pending messages in the Redis Stream consumer group (PEL count)",
)

# -- Model drift --

DRIFT_PSI = Gauge(
    "porter_model_drift_psi",
    "Population Stability Index comparing current vs baseline fraud_prob distribution",
)

DRIFT_FEATURE_PSI = Gauge(
    "porter_feature_drift_psi",
    "Per-feature PSI for top behavioural signals",
    ["feature"],
)

# -- Model metadata --

MODEL_INFO = Info(
    "porter_model",
    "Active model metadata (version, threshold, feature count)",
)
