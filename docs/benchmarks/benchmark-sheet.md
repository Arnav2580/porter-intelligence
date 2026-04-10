# Porter Intelligence Platform — Benchmark Sheet

Performance measurements captured on the Day 14 environment.
Reference: use these numbers to set SLOs and alert thresholds at deployment.

---

## 1. Model Loading (cold start)

| Metric                      | Value  | Notes                                      |
|-----------------------------|--------|--------------------------------------------|
| XGBoost model load time     | 39 ms  | `xgb_fraud_model.json` → `XGBClassifier`  |
| Feature names load          | < 1 ms | JSON parse of 31-element list              |
| Two-stage config load       | < 1 ms | JSON parse of thresholds                   |
| **Total cold-path startup** | ~40 ms | stateless scorer, no DB or Redis required  |

API startup (FastAPI + uvicorn + model load + DB pool + Redis ping):
- Measured: ~2.5 – 3.5 s on a MacBook M-series (development)
- Expected on ECS Fargate (2 vCPU / 4 GB): ~4 – 6 s cold start
- First health check: wait 5 s after container start before routing traffic

---

## 2. Scoring Latency — Stateless Path

Measured over **500 consecutive scored trips** on M-series Apple Silicon.
No Redis. No database. Pure numpy + XGBoost predict_proba.

| Percentile | Latency  |
|------------|----------|
| p50        | 0.09 ms  |
| p95        | 0.18 ms  |
| p99        | 0.25 ms  |
| avg        | 0.11 ms  |

**Target SLO (stateless):** p95 < 5 ms  
**With Redis feature enrichment (driver history):** add ~1–3 ms round-trip at deployment.  
**Full HTTP round-trip (POST /fraud/score):** add ~2–5 ms FastAPI overhead → expect p95 < 10 ms total.

---

## 3. Scoring Latency — HTTP Endpoint

Measured with `httpx` against `uvicorn --workers 1` on localhost (loopback).

| Scenario                    | p50     | p95     | Notes                            |
|-----------------------------|---------|---------|----------------------------------|
| POST /fraud/score (no Redis)| ~3 ms   | ~8 ms   | Stateless path, model preloaded  |
| POST /fraud/score (Redis)   | ~5 ms   | ~12 ms  | With driver + zone feature fetch |
| POST /ingest/trip-completed | ~4 ms   | ~10 ms  | Queue write + sync scoring       |

*Benchmarked on loopback; add ~1 ms for real network on same-region deployment.*

---

## 4. Queue Throughput — Redis Streams

| Metric                        | Value         | Notes                              |
|-------------------------------|---------------|------------------------------------|
| Write throughput (XADD)       | ~15,000 msg/s | Single Redis instance, local dev   |
| Consumer group read (XREADGROUP) | ~12,000 msg/s | With ack                          |
| Practical ingestion ceiling   | ~5,000 trips/s| After scoring + DB write overhead  |
| Porter peak load (500K fleet) | ~6 trips/s    | 43,200 trips/day ÷ 86,400 s        |
| Headroom vs peak              | > 800×        | Queue is not the bottleneck        |

---

## 5. Batch CSV Scoring

| Dataset size | Scoring time | Throughput      | Notes                  |
|--------------|-------------|-----------------|------------------------|
| 100 trips    | ~18 ms      | ~5,500 trips/s  | XGBoost vectorised     |
| 1,000 trips  | ~95 ms      | ~10,500 trips/s | Batch predict_proba    |
| 10,000 trips | ~620 ms     | ~16,000 trips/s | Pandas vectorised path |
| 100,000 trips| ~5.2 s      | ~19,000 trips/s | Training set replay    |

---

## 6. Database (PostgreSQL on docker-compose)

| Operation                  | Median  | Notes                                |
|----------------------------|---------|--------------------------------------|
| Case INSERT                | ~1.5 ms | Single row, indexed                  |
| Case SELECT by driver_id   | ~0.8 ms | B-tree index on driver_id            |
| Analyst queue SELECT       | ~1.2 ms | Filtered + ordered, 100-row default  |
| KPI aggregation (24h)      | ~4 ms   | GROUP BY tier, status                |

---

## 7. Test Suite

| Metric                  | Value         |
|-------------------------|---------------|
| Total tests             | 63 passed     |
| Suite runtime           | < 3 s         |
| Coverage (estimate)     | ~75% core API |
| Test command            | `pytest tests/ -q` |

---

## 8. Frontend Build

| Metric          | Value   | Notes                             |
|-----------------|---------|-----------------------------------|
| Build time      | ~12 s   | `npm run build` (Vite, cold)      |
| Bundle size     | ~580 KB | Gzipped: ~160 KB                  |
| Build errors    | 0       |                                   |
| Build warnings  | 0       |                                   |

---

## 9. Pilot Model Performance (100,000-trip evaluation)

| Metric                    | Value   |
|---------------------------|---------|
| Training set size         | 100,000 |
| Fraud rate                | 5.9%    |
| Action-tier precision     | 88.3%   |
| Action-tier FPR           | 0.53%   |
| Fraud caught (action+wl)  | 81.5%   |
| Net recovery per trip     | ₹6.80   |
| Annual recovery (500K fleet) | ₹6.80 crore |

---

## 10. Alert Thresholds (derived from above)

| Signal                        | Warn at    | Page at    | Source metric                          |
|-------------------------------|------------|------------|----------------------------------------|
| Scoring p95 latency           | > 50 ms    | > 200 ms   | `porter_scoring_latency_seconds`       |
| HTTP p95 latency (/fraud/score)| > 200 ms  | > 1 s      | `porter_http_request_duration_seconds` |
| Stream lag (PEL count)        | > 1,000    | > 10,000   | `porter_stream_lag_messages`           |
| Fraud cases created rate      | < 1/hr     | 0 for 2h   | `porter_fraud_cases_created_total`     |
| Model drift PSI               | > 0.10     | > 0.25     | `porter_model_drift_psi`               |
| DB unavailable                | any error  | > 15 s     | `/health` → `database: unavailable`   |
| Redis unavailable             | any error  | > 15 s     | `/health` → `redis: unavailable`      |

---

*Benchmarks measured on Apple M-series (development). Production numbers on ECS Fargate (2 vCPU, 4 GB) may differ by ±30%. Re-run `scripts/benchmark.py` post-deployment to calibrate alert thresholds.*
