"""
Porter Intelligence Platform — API Request/Response Schemas
All Pydantic models for API validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class TripScoreRequest(BaseModel):
    """Single trip record for real-time fraud scoring."""
    trip_id:               str
    driver_id:             str
    vehicle_type:          str
    pickup_zone_id:        str
    dropoff_zone_id:       str
    pickup_lat:            float
    pickup_lon:            float
    dropoff_lat:           float
    dropoff_lon:           float
    declared_distance_km:  float
    declared_duration_min: float
    fare_inr:              float
    payment_mode:          str          # upi / cash / credit
    surge_multiplier:      float
    requested_at:          str          # ISO datetime string
    is_night:              bool
    hour_of_day:           int
    day_of_week:           int
    is_peak_hour:          bool
    zone_demand_at_time:   float
    status:                str
    customer_complaint_flag: bool = False


class TripScoreResponse(BaseModel):
    """Fraud score response — two-stage tiered output."""
    trip_id:            str

    # Raw probability (unchanged)
    fraud_probability:  float = Field(ge=0.0, le=1.0)

    # Two-stage tier result
    tier:               str   # action / watchlist / clear
    tier_label:         str   # ACTION REQUIRED / WATCHLIST / CLEAR
    tier_color:         str   # hex color for dashboard

    # Legacy fields preserved for backward compat
    is_fraud_predicted: bool
    fraud_risk_level:   str   # CRITICAL / HIGH / MEDIUM / LOW

    # Ops team instruction
    action_required:    str
    auto_escalate:      bool  # watchlist auto-escalation flag

    # Explanation
    top_signals:        List[str]
    confidence:         str   # "high" / "medium" / "low"
    scored_at:          str


class ZoneFraudRate(BaseModel):
    zone_id:     str
    zone_name:   str
    city:        str
    lat:         float
    lon:         float
    fraud_rate:  float
    fraud_count: int
    risk_level:  str


class HeatmapResponse(BaseModel):
    zones:        List[ZoneFraudRate]
    total_trips:  int
    total_fraud:  int
    generated_at: str


class FraudFeedItem(BaseModel):
    trip_id:       str
    driver_id:     str
    zone_id:       str
    fraud_type:    str
    confidence:    float
    fare_inr:      float
    recoverable:   float
    flagged_at:    str


class LiveFeedResponse(BaseModel):
    items:       List[FraudFeedItem]
    total_shown: int


class KPISummaryResponse(BaseModel):
    window_label:           str
    total_trips:            int
    fraud_detected:         int
    fraud_rate_pct:         float
    baseline_caught:        int
    xgboost_caught:         int
    improvement_pct:        float
    net_recoverable_inr:    float
    net_recoverable_per_trip: float
    fpr_pct:                float
    annual_recovery_crore:  float
    royalty_crore:          float
    pilot_criteria_pass:    Dict[str, bool]


class DriverRiskResponse(BaseModel):
    driver_id:         str
    risk_score:        float
    risk_level:        str
    recent_fraud_rate: float
    cancel_velocity:   float
    ring_member:       bool
    recommendation:    str
