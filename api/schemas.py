"""
Porter Intelligence Platform — API Request/Response Schemas
All Pydantic models for API validation.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Union


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
    evaluation_window_label: str = Field(
        description="Human-readable description of the evaluation window."
    )
    total_trips: int = Field(
        description="Total trips evaluated in the benchmark window."
    )
    fraud_detected: int = Field(
        description="High-confidence fraud cases caught by the benchmark model."
    )
    fraud_rate_pct: float = Field(
        description="Observed fraud incidence within the evaluation dataset."
    )
    baseline_caught: int = Field(
        description="Fraud cases caught by the baseline ruleset."
    )
    xgboost_caught: int = Field(
        description="Fraud cases caught by the scored model."
    )
    improvement_pct: float = Field(
        description="Detection lift over the baseline ruleset."
    )
    net_recoverable_inr: float = Field(
        description="Estimated net recoverable value in INR for the evaluated window."
    )
    net_recoverable_per_trip: float = Field(
        description="Estimated net recoverable value per trip."
    )
    fpr_pct: float = Field(
        description="False positive rate for the scored model."
    )
    projected_annual_recovery_crore: float = Field(
        description="Annualised recovery projection in crore INR."
    )
    performance_criteria: Dict[str, bool] = Field(
        description="Pass/fail summary for benchmark performance gates."
    )


class DriverRiskResponse(BaseModel):
    driver_id:         str
    risk_score:        float
    risk_level:        str
    recent_fraud_rate: float
    cancel_velocity:   float
    ring_member:       bool
    recommendation:    str


class ROICalculationRequest(BaseModel):
    gmv_crore: float = Field(
        gt=0,
        description="Annual GMV in crore INR used for savings-to-GMV framing.",
    )
    trips_per_day: int = Field(
        gt=0,
        description="Average completed trips per day.",
    )
    fraud_rate_pct: float = Field(
        gt=0,
        le=100,
        description="Estimated fraud or leakage incidence as a percent of trips.",
    )
    platform_price_crore: float = Field(
        default=3.25,
        gt=0,
        description="Commercial price used for payback and ROI calculations.",
    )


class ROIScenario(BaseModel):
    scenario: str
    realization_multiplier: float
    annual_savings_crore: float
    monthly_savings_lakh: float
    payback_months: float
    payback_days: int
    roi_pct: float
    savings_pct_of_gmv: float
    savings_bps_of_gmv: float
    note: str


class ROICalculationResponse(BaseModel):
    annual_savings_crore: float
    payback_months: float
    roi_pct: float
    benchmark_net_recoverable_per_trip: float
    benchmark_fraud_rate_pct: float
    platform_price_crore: float
    annual_trip_volume: int
    savings_pct_of_gmv: float
    savings_bps_of_gmv: float
    scenarios: List[ROIScenario]
    assumptions: Dict[str, Union[float, int, str]]
