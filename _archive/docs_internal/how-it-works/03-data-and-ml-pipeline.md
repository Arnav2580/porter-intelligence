# 03 — Data And ML Pipeline

[Index](./README.md) | [Prev: Architecture](./02-architecture-deep-dive.md) | [Next: API Reference](./04-api-reference.md)

This document explains every part of the machine learning system: how data is generated, how features are engineered, how models are trained and evaluated, and how scoring works in production.

---

## Overview

The platform has four ML components:

| Component | Model | Purpose | Source File |
|---|---|---|---|
| Fraud detection | XGBoost | Score every trip for fraud probability | `model/train.py`, `model/scoring.py` |
| Feature engineering | Pandas | Transform raw trips into 35 numeric features | `model/features.py` |
| Demand forecasting | Prophet | Predict hourly trip demand per zone | `model/demand.py` |
| Driver intelligence | Rule-based + ML | Risk profiles, peer comparison, ring detection | `model/driver_intelligence.py` |
| Route efficiency | Rule-based | Dead mile analysis, vehicle reallocation | `model/route_efficiency.py` |
| Natural language query | Keyword + Ollama | Plain-English queries over fraud data | `model/query.py` |

---

## 1. Synthetic Data Generation

All training data is generated synthetically using the `generator/` package. This is deliberate: Porter has not yet shared live data, so the platform proves its capability on realistic synthetic data at Porter-like scale.

### Generator modules

| Module | What it generates | Key parameters |
|---|---|---|
| `generator/config.py` | Master constants | 50K drivers, 100K customers, 500K trips |
| `generator/cities.py` | 22 city profiles with zones | Zone coordinates, demand patterns, fraud bias |
| `generator/drivers.py` | Driver profiles | Account age, rating, vehicle, verification, fraud propensity |
| `generator/customers.py` | Customer profiles | Location, complaint history |
| `generator/trips.py` | Trip records | Fare, distance, duration, payment, timestamps |
| `generator/fraud.py` | Fraud injection | 6 fraud types injected at 4.7% base rate |

### Fraud types

The generator injects six fraud archetypes, each modifying trip records differently:

| Fraud Type | % of Fraud | What It Simulates | Detection Signal |
|---|---|---|---|
| `fake_trip` | 28% | Driver never moved (GPS fraud) | `distance_time_ratio` near zero |
| `cash_extortion` | 22% | Driver demands cash above meter | `fare_to_expected_ratio` > 2x + cash payment |
| `route_deviation` | 20% | Detour to inflate fare | `distance_vs_haversine_ratio` elevated |
| `fake_cancellation` | 15% | Accept-and-cancel ring coordination | `driver_cancellation_velocity_1hr` >= 3 |
| `duplicate_trip` | 8% | Same trip billed twice | Duplicate trip_id patterns |
| `inflated_distance` | 7% | Declare more km than possible | `declared_distance_km` vs haversine |

### Driver fraud propensity

Drivers are segmented into three fraud propensity groups:

| Segment | % of Drivers | Fraud Probability Range |
|---|---|---|
| Honest | 91% | 0.00 - 0.15 |
| Occasional | 6% | 0.15 - 0.50 |
| Chronic | 3% | 0.50 - 1.00 |

Additional propensity adjustments are applied for:
- Cash payment preference: +0.30
- Unverified account: +0.20
- New driver (< 180 days): +0.15
- Low rating (< 3.8): +0.25
- High cancellation rate (> 20%): +0.20

### Data splits

Generated trips are split into two windows:

| Window | Duration | Purpose |
|---|---|---|
| Historical | 45 days | Model training and validation |
| Live evaluation | 14 days | Simulated production scoring test |

The model never sees live_eval data during training. All benchmark metrics are computed on the live_eval window.

---

## 2. Feature Engineering

**Source:** `model/features.py`

The feature pipeline transforms raw trip records into a 35-feature numeric matrix. Features are computed in three stages.

### Stage 1: Trip-level features (`compute_trip_features`)

These are derived from a single trip record with no cross-trip lookups.

| Feature | Computation | Why It Matters |
|---|---|---|
| `declared_distance_km` | Raw field | Baseline distance |
| `declared_duration_min` | Raw field | Baseline duration |
| `fare_inr` | Raw field | Trip fare |
| `surge_multiplier` | Raw field | Peak pricing indicator |
| `zone_demand_at_time` | Raw field | Local demand context |
| `fare_to_expected_ratio` | `fare / (base_fare + per_km * distance)` | **Key fraud signal** — inflated fares |
| `distance_time_ratio` | `distance / duration` | Fake trips have near-zero ratio |
| `fare_per_km` | `fare / distance` | Overcharging indicator |
| `pickup_dropoff_haversine_km` | Haversine formula on lat/lon | Straight-line distance |
| `distance_vs_haversine_ratio` | `declared_distance / haversine` | Route deviation detector |
| `hour_of_day` | Extracted from timestamp | Temporal pattern |
| `day_of_week` | Extracted from timestamp | Temporal pattern |
| `is_night` | `hour >= 22 or hour <= 5` | Night = 2x fraud rate |
| `is_peak_hour` | `hour in {8,9,10,18,19,20}` | Peak demand context |
| `is_friday` | `day_of_week == 4` | Friday = elevated fraud |
| `is_late_month` | `day >= 25` | End-of-month payout pressure |
| `payment_is_cash` | One-hot encoded | **Key fraud signal** — cash extortion |
| `payment_is_credit` | One-hot encoded | Payment context |
| `same_zone_trip` | `pickup_zone == dropoff_zone` | Short-haul fraud indicator |
| `is_cancelled` | Status check | Cancellation fraud |

### Stage 2: Driver profile features (`compute_driver_features`)

These join driver metadata onto each trip record.

| Feature | Source | Why It Matters |
|---|---|---|
| `driver_account_age_days` | Driver profile | New accounts = higher risk |
| `driver_rating` | Driver profile | Low rating correlates with fraud |
| `driver_lifetime_trips` | Driver profile | Experience level |
| `driver_verification_encoded` | 0=verified, 1=pending, 2=unverified | Unverified = higher risk |
| `driver_payment_type_encoded` | 0=UPI, 1=bank, 2=cash | Cash preference = risk signal |

### Stage 3: Behavioural sequence features (`compute_behavioural_sequence_features`)

These require cross-trip lookups within a driver's history. They are the **moat features** — expensive to compute, impossible to replicate with simple SQL rules.

| Feature | Window | Computation | Why It Matters |
|---|---|---|---|
| `driver_cancellation_velocity_1hr` | 1 hour | Cancellations in prior 60 minutes | **Ring coordination signal** — 3+ = escalate |
| `driver_cancel_rate_rolling_7d` | 7 days | Cancel rate in prior week | Chronic cancellation pattern |
| `driver_dispute_rate_rolling_14d` | 14 days | Dispute rate in prior 2 weeks | Real-time fraud proxy (no label leakage) |
| `driver_trips_last_24hr` | 24 hours | Trip count in prior day | Activity volume context |
| `driver_cash_trip_ratio_7d` | 7 days | % cash trips in prior week | Cash preference trending |
| `zone_fraud_rate_rolling_7d` | 7 days | Historical fraud rate for pickup zone | Zone-level risk clustering |

**Important:** Zone fraud rates are computed from the historical window only, preventing data leakage into the evaluation window.

### Feature matrix assembly (`build_feature_matrix`)

```
Raw trips DataFrame
    → compute_trip_features()      (20 features)
    → compute_driver_features()    (5 features)
    → compute_behavioural_sequence_features()  (6 features + 4 from raw fields)
    → Enforce FEATURE_COLUMNS order (35 total)
    → Fill NaN with 0.0
    → Cast all to float
    → Return X (features), y (target), weights (confidence)
```

Fraud trips receive confidence-weighted sample weights (0.5-1.0). Non-fraud trips always have weight 1.0. This means high-confidence fraud labels train with more weight than ambiguous ones.

---

## 3. Model Training

**Source:** `model/train.py`

### Training pipeline (`run_training_pipeline`)

The full pipeline runs in 9 steps:

```
Step 1: Split trips into historical (45 days) and live_eval (14 days)
Step 2: Build feature matrices for each window
Step 3: Run baseline rules on live_eval (Stage 1)
Step 4: Train XGBoost on 80% of historical (Stage 2)
Step 5: Tune classification threshold on 20% historical validation
Step 6: Evaluate XGBoost on live_eval
Step 7: Print comparison table (baseline vs XGBoost)
Step 8: Save model weights and evaluation report
Step 9: Check pilot success criteria (pass/fail)
```

### Baseline rule system (Stage 1)

The baseline represents what Porter's ops team does manually — three simple rules:

| Rule | Logic | Targets |
|---|---|---|
| Rule 1 | Cash payment AND fare > 2x expected | Cash extortion |
| Rule 2 | Distance/time ratio < 0.1 AND distance > 2km | Fake trips |
| Rule 3 | Driver cancellation velocity >= 3 in last hour | Cancellation rings |

Any rule triggered = predicted fraud. This is the comparison benchmark.

### XGBoost configuration

```python
XGBClassifier(
    n_estimators          = 500,
    max_depth             = 6,
    learning_rate         = 0.05,
    subsample             = 0.8,
    colsample_bytree      = 0.8,
    scale_pos_weight      = auto,   # n_non_fraud / n_fraud
    eval_metric           = "aucpr", # precision-recall AUC
    early_stopping_rounds = 50,
    random_state          = 42,
)
```

Key design choices:
- **`scale_pos_weight`**: Automatically handles class imbalance (fraud is ~5% of trips)
- **`aucpr`**: Precision-recall AUC is the right metric for imbalanced datasets (not ROC AUC)
- **`early_stopping_rounds=50`**: Prevents overfitting by monitoring validation loss
- **`sample_weight`**: Confidence-weighted training — high-confidence fraud cases train harder
- **Internal 90/10 split**: Within the 80% training set, a 90/10 split is used for early stopping

### Threshold tuning

The optimal classification threshold is found by grid search:

```
Search space: 0.10 to 0.96 in 0.01 steps
Constraint:   FPR must stay <= 8% (hard ceiling)
Objective:    Maximise net_recoverable_per_trip
```

This means the threshold is chosen to maximise financial recovery while keeping false alarms tolerable for the ops team.

### Model artifacts saved

| File | Path | Contents |
|---|---|---|
| XGBoost model | `model/weights/xgb_fraud_model.json` | Serialised XGBoost model |
| Feature names | `model/weights/feature_names.json` | Ordered list of 35 feature names |
| Threshold | `model/weights/threshold.json` | `{"threshold": 0.xx}` |
| Evaluation report | `data/raw/evaluation_report.json` | Full metrics, feature importance, pilot pass/fail |

### Running the training pipeline

```bash
python -m model.train
```

This generates data (if not already on disk), trains the model, evaluates it, and saves all artifacts.

---

## 4. Two-Stage Scoring

**Source:** `model/scoring.py`

Instead of binary fraud/not-fraud classification, the platform uses a **two-stage tiered scoring system**.

### Why two stages?

- Binary classification at high sensitivity creates too many false alarms
- Two stages give analysts a priority system: handle ACTION first, then WATCHLIST
- Watchlist escalation catches coordinated fraud that single-trip scoring misses
- This design is standard in financial fraud detection (Visa, Mastercard use similar tiering)

### Tier definitions

| Tier | Threshold | Color | Action | Auto-escalate |
|---|---|---|---|---|
| **ACTION** | >= 0.94 | Red (#EF4444) | Investigate immediately. No secondary review needed. | No |
| **WATCHLIST** | 0.45 - 0.88 | Amber (#F59E0B) | Monitor. Escalates to ACTION if driver appears 3+ times in 24hrs. | Yes (3 in 24h) |
| **CLEAR** | < 0.45 | Green (#22C55E) | No action required. | No |

### Watchlist escalation engine

```python
def check_watchlist_escalation(driver_id, trips_df, window_hours=24):
    """
    A driver with 3+ watchlist trips in 24 hours
    is escalated automatically — this is the ring
    coordination detection signal.
    """
```

This catches fraud rings where individual trips might not exceed the 0.94 action threshold, but the pattern of repeated watchlist-level trips reveals coordinated fraud.

### Tier evaluation metrics

The `evaluate_two_stage()` function computes metrics separately for each tier:

- **Action tier precision**: % of action-tier trips that are actually fraud
- **Action tier FPR**: False positives as % of all clean trips
- **Watchlist recoverable**: Estimated at 50% (needs analyst investigation)
- **Combined system metrics**: Action + watchlist fraud caught, net recovery

### Pilot success criteria

| Criterion | Target | Purpose |
|---|---|---|
| Detection improvement vs baseline | >= 25% | XGBoost must beat manual rules significantly |
| False positive rate | <= 8% | Ops team cannot handle more than 8% false alarms |
| Net recoverable per trip | >= Rs 0.50 | Financial viability threshold |

---

## 5. Demand Forecasting

**Source:** `model/demand.py`

### What it does

Trains one Facebook Prophet model per zone on historical trip data. Forecasts hourly trip demand for the next 24 hours with uncertainty intervals.

### Why Prophet?

- Trip demand has strong daily + weekly seasonality
- Training data is time-series by nature
- Forecasts need uncertainty intervals (upper/lower bounds)
- No GPU required — trains in seconds per zone

### Prophet configuration

```python
Prophet(
    yearly_seasonality       = False,   # only 45 days of data
    weekly_seasonality       = True,    # 7-day patterns clear
    daily_seasonality        = True,    # hourly patterns clear
    seasonality_mode         = "multiplicative",  # surge is multiplicative
    changepoint_prior_scale  = 0.05,    # conservative
    interval_width           = 0.80,    # 80% uncertainty interval
)
```

### Additional regressors

Three contextual regressors are added to improve forecast accuracy:

| Regressor | Type | Impact |
|---|---|---|
| `is_weekend` | Boolean | Weekend demand patterns differ |
| `is_friday` | Boolean | Friday shows unique demand spike |
| `is_late_month` | Boolean | End-of-month payout period |

### Data preparation

1. Filter trips by zone
2. Floor timestamps to hourly
3. Count trips per hour
4. Fill missing hours with 0 (Prophet needs continuous series)
5. Add regressor columns
6. Minimum 50 trips required per zone to train a model

### Forecast output

For each hour in the next 24:

| Field | Description |
|---|---|
| `hour_label` | e.g., "19:00" |
| `yhat` | Predicted trip count |
| `yhat_lower` | Lower bound (80% CI) |
| `yhat_upper` | Upper bound (80% CI) |
| `demand_multiplier` | Normalised to base rate |
| `surge_expected` | True if multiplier > 1.8 |
| `confidence_pct` | Width of interval as % of prediction |

### Model artifacts

| File | Path |
|---|---|
| Prophet models (pickle) | `model/weights/demand_models.pkl` |
| Zone metadata | `model/weights/demand_models_meta.json` |

### Running demand training

```bash
python -m model.demand
```

---

## 6. Driver Intelligence Engine

**Source:** `model/driver_intelligence.py`

### What it does

Computes comprehensive risk profiles for individual drivers. Three core outputs:

1. **Risk timeline**: 30-day daily fraud probability trend
2. **Peer comparison**: Driver metrics vs zone median
3. **Ring intelligence**: Ring membership and coordination data

### Risk timeline computation

For each day in the last 30 days:
1. Count trips and fraud trips
2. Compute 3-day rolling fraud rate
3. Calculate risk score:
   ```
   risk_score = fraud_rate_rolling * 10
               + 0.3 if any fake_cancellation that day
               + 0.4 if any cash_extortion that day
   clipped to [0.0, 1.0]
   ```
4. Assign risk level: CRITICAL (> 0.7), HIGH (> 0.4), MEDIUM (> 0.2), LOW

### Peer comparison

Compares a driver's metrics against the median driver in the same zone:

| Metric | Flag Threshold |
|---|---|
| Fraud rate | > 2x zone median |
| Cancellation rate | > 2x zone median |
| Cash trip ratio | > 2.5x zone median |
| Average fare | > 1.8x zone median |
| Trips per day | Not flagged (high volume is normal) |

Each metric includes a percentile rank showing where the driver falls among all zone drivers.

### Ring intelligence

Detects fraud ring membership and coordination:
- If driver has a `fraud_ring_id`: reports ring size, role (leader/member), zone, coordination events
- If not: checks for suspected ring membership (> 5 cancellations AND > 25% cancel rate)
- Ring members get a 1.5x risk multiplier

### Recommendation engine

Based on the combined intelligence, generates one of four actions:

| Action | Trigger | Priority |
|---|---|---|
| SUSPEND | Risk > 0.7 OR ring leader | IMMEDIATE |
| FLAG_REVIEW | Risk 0.4-0.7 OR ring member | HIGH |
| MONITOR | Rising trend OR suspected ring OR risk 0.2-0.4 | MEDIUM |
| CLEAR | Risk < 0.2 and no flags | LOW |

### API endpoint

`GET /driver-intelligence/{driver_id}` returns the full profile: timeline, peer comparison, ring intelligence, recommendation, and summary stats.

---

## 7. Route Efficiency Engine

**Source:** `model/route_efficiency.py`

### What it does

Computes fleet utilisation metrics and generates vehicle reallocation suggestions. Three computations:

### Dead mile analysis

Dead miles are trips where the driver travels but generates no revenue:
- Customer cancels after driver started moving
- Driver accepts a trip far from pickup (> 8 minute accept delay)

Per-zone output: dead mile rate, estimated dead km, cost per day (at Rs 12/km fuel + wear).

### Hourly utilisation heatmap

For each zone, vehicle type, and hour of day:
- Count active vehicles
- Estimate idle vehicles (active in previous hour but not this hour, in a demand zone)
- Compute utilisation = active / (active + idle)
- Flag opportunities where idle vehicles exist near high-demand zones

### Reallocation suggestions

For each idle vehicle pool:
1. Find demand zones within 8km
2. Estimate trips if reallocated (based on demand multiplier)
3. Calculate expected revenue
4. Assign urgency: IMMEDIATE (> 2.0x demand), HIGH (> 1.7x), MEDIUM
5. Sort by expected revenue, return top 8

### Fleet summary KPIs

| Metric | Description |
|---|---|
| `overall_utilisation` | Fleet-wide average (target: > 60%) |
| `total_dead_mile_rate` | Weighted average dead mile % (target: < 20%) |
| `total_dead_cost_per_day` | Rs wasted on dead miles daily |
| `idle_vehicle_hours_now` | Total idle capacity at current hour |
| `reallocation_opportunity_inr` | Rs recoverable by acting on suggestions |

---

## 8. Natural Language Query Engine

**Source:** `model/query.py`

### What it does

Allows ops managers to query fraud data in plain English. Uses keyword matching for common queries with optional Ollama LLM fallback.

### Supported query types

| Query Type | Trigger Keywords | Data Source |
|---|---|---|
| Fraud rings | "ring", "organised", "coordinated" | `drivers_df` aggregation |
| High-risk drivers | "driver", "risk", "highest" | `trips_df` aggregation |
| Zone analysis | "zone", "area", "koramangala" | `trips_df` aggregation |
| KPI summary | "summary", "total", "how much" | `evaluation_report.json` |
| Fraud types | "type", "fake", "extortion" | `trips_df` aggregation |
| Methodology | "how", "explain", "features" | Static + feature importance |

### Architecture

```
Query arrives
    → Keyword matching (fast path, < 50ms)
    → If matched: build structured answer from data
    → If not matched: fall back to Ollama LLM
        → Inject structured context (no raw rows)
        → Ollama generates answer from context
    → Return {query, answer, source, response_ms}
```

### LLM fallback (Ollama)

- Model: `llama3` (local, no API key needed)
- Temperature: 0.1 (deterministic)
- Max tokens: 300
- Context: structured aggregates from evaluation report (no raw trip data)
- If Ollama is not running: returns a helpful message listing available query types

---

## Model Performance Summary

### Benchmark results (synthetic data)

| Metric | Baseline (Rules) | XGBoost (Two-Stage) |
|---|---|---|
| Action tier precision | ~60% | 88.3% |
| False positive rate | ~12% | 0.53% |
| Fraud caught | ~40% | 70%+ |
| Net recoverable per trip | ~Rs 0.30 | Rs 0.80+ |

### Pilot success criteria

| Criterion | Target | Result |
|---|---|---|
| Detection improvement | >= 25% | PASS |
| False positive rate | <= 8% | PASS (0.53%) |
| Net recoverable per trip | >= Rs 0.50 | PASS |

### Important caveat

These are **benchmark results on synthetic data**. They demonstrate that the model architecture works. Real production precision will be determined during shadow-mode validation on Porter's actual data, judged by Porter's own analysts.

---

## Next

- [API Reference](./04-api-reference.md) — every endpoint documented
- [Ingestion and Shadow Mode](./05-ingestion-and-shadow-mode.md) — how data flows in
