"""
Porter Intelligence Platform — Demand Prediction Model

Trains one Prophet model per zone using historical trip data.
Forecasts hourly trip demand for the next 24 hours.

Prophet is appropriate here because:
  - Trip demand has strong daily + weekly seasonality
  - Training data is time-series by nature
  - Forecasts need uncertainty intervals (upper/lower bounds)
  - No GPU required — trains in seconds per zone on M4
"""

import numpy as np
import pandas as pd
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

from generator.config import (
    RANDOM_SEED, DATA_RAW, MODEL_WEIGHTS,
    HISTORICAL_DAYS,
)
from generator.cities import ZONES, CITY_ZONES

console = Console()


# ── Data preparation ──────────────────────────────────────────

def prepare_demand_series(
    trips_df: pd.DataFrame,
    zone_id: str,
    min_trips: int = 50,
) -> Optional[pd.DataFrame]:
    """
    Prepare a Prophet-compatible time series for one zone.

    Prophet expects a DataFrame with columns:
      ds: datetime (hourly)
      y:  trip count (target)

    Additional regressors added:
      is_weekend:    bool -> Prophet regressor
      is_friday:     bool -> Prophet regressor
      is_late_month: bool -> Prophet regressor

    Args:
        trips_df: Historical trips only (data_split == historical)
        zone_id:  Zone to prepare series for
        min_trips: Minimum trips required to fit a model

    Returns:
        DataFrame ready for Prophet.fit() or None if insufficient data
    """
    zone_trips = trips_df[
        trips_df["pickup_zone_id"] == zone_id
    ].copy()

    if len(zone_trips) < min_trips:
        return None

    zone_trips["requested_at"] = pd.to_datetime(
        zone_trips["requested_at"], format="ISO8601",
    )

    # Floor to hour for aggregation
    zone_trips["hour_floor"] = zone_trips["requested_at"].dt.floor("h")

    # Count trips per hour
    hourly = (
        zone_trips.groupby("hour_floor")
        .size()
        .reset_index(name="y")
        .rename(columns={"hour_floor": "ds"})
    )

    # Fill missing hours with 0 (Prophet needs continuous series)
    if len(hourly) > 1:
        full_range = pd.date_range(
            start=hourly["ds"].min(),
            end=hourly["ds"].max(),
            freq="h",
        )
        hourly = (
            hourly.set_index("ds")
            .reindex(full_range, fill_value=0)
            .reset_index()
            .rename(columns={"index": "ds"})
        )

    # Add regressors
    hourly["is_weekend"]    = hourly["ds"].dt.dayofweek.ge(5).astype(float)
    hourly["is_friday"]     = hourly["ds"].dt.dayofweek.eq(4).astype(float)
    hourly["is_late_month"] = hourly["ds"].dt.day.ge(25).astype(float)

    return hourly


# ── Model training ────────────────────────────────────────────

def train_demand_models(
    trips_df: pd.DataFrame,
    zones_to_train: Optional[List[str]] = None,
) -> Dict[str, object]:
    """
    Train one Prophet model per zone on historical trip data.

    Args:
        trips_df:       Full trips DataFrame (all splits)
        zones_to_train: Zone IDs to train on.
                        Defaults to all Bangalore zones.

    Returns:
        Dict of {zone_id: fitted Prophet model}

    Prophet config:
      yearly_seasonality:  False (only 90 days of data)
      weekly_seasonality:  True  (7-day patterns are clear)
      daily_seasonality:   True  (hourly patterns are clear)
      seasonality_mode:    multiplicative (surge is multiplicative)
      changepoint_prior_scale: 0.05 (conservative)
      interval_width:      0.80  (80% uncertainty interval)
    """
    from prophet import Prophet
    import logging
    logging.getLogger("prophet").setLevel(logging.WARNING)
    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)

    # Default to Bangalore zones
    if zones_to_train is None:
        zones_to_train = CITY_ZONES.get("bangalore", [])

    # Use historical window only for training
    hist_df = trips_df[
        trips_df["data_split"] == "historical"
    ].copy()

    models: Dict[str, object] = {}
    skipped = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]{task.description}"),
        BarColumn(),
        TextColumn("[green]{task.completed}/{task.total}"),
        console=console,
    ) as progress:
        task = progress.add_task(
            "Training demand models...",
            total=len(zones_to_train),
        )

        for zone_id in zones_to_train:
            series = prepare_demand_series(hist_df, zone_id)

            if series is None or len(series) < 24:
                skipped.append(zone_id)
                progress.advance(task)
                continue

            try:
                model = Prophet(
                    yearly_seasonality       = False,
                    weekly_seasonality       = True,
                    daily_seasonality        = True,
                    seasonality_mode         = "multiplicative",
                    changepoint_prior_scale  = 0.05,
                    interval_width           = 0.80,
                )

                # Add contextual regressors
                model.add_regressor("is_weekend")
                model.add_regressor("is_friday")
                model.add_regressor("is_late_month")

                model.fit(series)
                models[zone_id] = model

            except Exception as e:
                skipped.append(zone_id)
                console.print(
                    f"[yellow]  {zone_id} failed: {e}[/yellow]"
                )

            progress.advance(task)

    if skipped:
        console.print(
            f"[yellow]Skipped {len(skipped)} zones "
            f"(insufficient data): {skipped}[/yellow]"
        )

    console.print(
        f"[green]Trained {len(models)} demand models[/green]"
    )

    return models


# ── Forecasting ───────────────────────────────────────────────

def forecast_zone(
    model: object,
    zone_id: str,
    hours_ahead: int = 24,
) -> pd.DataFrame:
    """
    Generate a 24-hour demand forecast for one zone.

    Returns DataFrame with columns:
      hour:             int (0-23, relative to now)
      ds:               datetime
      hour_label:       str (e.g. "19:00")
      yhat:             predicted trip count
      yhat_lower:       lower bound (80% interval)
      yhat_upper:       upper bound (80% interval)
      demand_multiplier: yhat normalised to base rate
      surge_expected:   bool (multiplier > 1.8)
      confidence_pct:   int (width of interval as % of yhat)
    """
    import datetime as dt

    now = dt.datetime.now().replace(minute=0, second=0, microsecond=0)

    future_dates = pd.date_range(
        start=now,
        periods=hours_ahead,
        freq="h",
    )

    future = pd.DataFrame({"ds": future_dates})
    future["is_weekend"]    = future["ds"].dt.dayofweek.ge(5).astype(float)
    future["is_friday"]     = future["ds"].dt.dayofweek.eq(4).astype(float)
    future["is_late_month"] = future["ds"].dt.day.ge(25).astype(float)

    forecast = model.predict(future)

    # Normalise to demand multiplier
    base_rate = max(forecast["yhat"].mean(), 1.0)
    result = forecast[[
        "ds", "yhat", "yhat_lower", "yhat_upper",
    ]].copy()

    result["hour"]              = range(hours_ahead)
    result["hour_label"]        = result["ds"].dt.strftime("%H:00")
    result["yhat"]              = result["yhat"].clip(lower=0).round(1)
    result["yhat_lower"]        = result["yhat_lower"].clip(lower=0).round(1)
    result["yhat_upper"]        = result["yhat_upper"].clip(lower=0).round(1)
    result["demand_multiplier"] = (result["yhat"] / base_rate).round(3)
    result["surge_expected"]    = result["demand_multiplier"] > 1.8
    result["confidence_pct"]    = (
        (result["yhat_upper"] - result["yhat_lower"])
        / result["yhat"].clip(lower=1) * 100
    ).round(1)

    return result.reset_index(drop=True)


# ── Save / Load ───────────────────────────────────────────────

def save_demand_models(
    models: Dict[str, object],
    path: Path = MODEL_WEIGHTS,
) -> None:
    """Save all trained Prophet models to disk."""
    path.mkdir(parents=True, exist_ok=True)
    save_path = path / "demand_models.pkl"

    with open(save_path, "wb") as f:
        pickle.dump(models, f)

    # Also save zone list for quick reference
    meta_path = path / "demand_models_meta.json"
    with open(meta_path, "w") as f:
        json.dump({
            "zones_trained": list(models.keys()),
            "trained_at":    datetime.now().isoformat(),
            "hours_ahead":   24,
        }, f, indent=2)

    console.print(
        f"[green]Saved {len(models)} models -> {save_path}[/green]"
    )


def load_demand_models(
    path: Path = MODEL_WEIGHTS,
) -> Dict[str, object]:
    """Load trained Prophet models from disk."""
    load_path = path / "demand_models.pkl"

    if not load_path.exists():
        return {}

    with open(load_path, "rb") as f:
        return pickle.load(f)


# ── Test block ────────────────────────────────────────────────

if __name__ == "__main__":
    console.rule("[cyan]Demand Model — Validation[/cyan]")

    # Generate sample data
    console.print("[dim]Generating sample trips...[/dim]")
    from generator.drivers import generate_drivers
    from generator.customers import generate_customers
    from generator.trips import generate_trips
    from generator.fraud import inject_fraud

    drivers_df   = generate_drivers(n=5000, city_filter="bangalore")
    customers_df = generate_customers(n=5000, city_filter="bangalore")
    trips_df     = generate_trips(
        drivers_df, customers_df,
        n=20_000, city_filter="bangalore",
    )
    trips_df = inject_fraud(trips_df, drivers_df)

    # Train models
    console.rule("[cyan]Training Prophet Models[/cyan]")
    models = train_demand_models(trips_df)

    assert len(models) > 0, "No models trained"

    # Test forecast for Koramangala
    assert "blr_koramangala" in models, \
        "Koramangala model must be trained"

    forecast = forecast_zone(
        models["blr_koramangala"],
        "blr_koramangala",
        hours_ahead=24,
    )

    # ── Assertions ─────────────────────────────────────────
    assert len(forecast) == 24, \
        "Must forecast exactly 24 hours"
    assert forecast["yhat"].ge(0).all(), \
        "Predictions must be non-negative"
    assert (forecast["yhat_upper"] >= forecast["yhat"]).all(), \
        "Upper bound must exceed prediction"
    assert (forecast["yhat"] >= forecast["yhat_lower"]).all(), \
        "Prediction must exceed lower bound"

    # Peak hours must show higher demand than dead hours
    peak_demand = forecast[
        forecast["ds"].dt.hour.isin([8, 9, 18, 19, 20])
    ]["demand_multiplier"].mean()
    dead_demand = forecast[
        forecast["ds"].dt.hour.isin([2, 3, 4])
    ]["demand_multiplier"].mean()

    assert peak_demand > dead_demand, \
        "Peak hours must have higher demand than dead hours"

    # ── Forecast table ──────────────────────────────────────
    table = Table(
        title="Koramangala — 24hr Demand Forecast (Prophet)",
    )
    table.add_column("Hour",       justify="right", style="cyan")
    table.add_column("Trips/hr",   justify="right")
    table.add_column("Multiplier", justify="right")
    table.add_column("CI",         justify="right", style="dim")
    table.add_column("Surge",      justify="center")

    for _, row in forecast.iterrows():
        surge = "SURGE" if row["surge_expected"] else ""
        mult  = row["demand_multiplier"]
        color = (
            "red"    if mult > 1.8 else
            "yellow" if mult > 1.3 else
            "green"
        )
        table.add_row(
            row["hour_label"],
            f"{row['yhat']:.1f}",
            f"[{color}]{mult:.3f}x[/{color}]",
            f"+/-{row['confidence_pct']:.0f}%",
            surge,
        )

    console.print(table)

    # ── Summary stats ───────────────────────────────────────
    summary = Table(title="Demand Model Summary")
    summary.add_column("Metric",  style="cyan")
    summary.add_column("Value",   style="green")
    summary.add_row("Zones trained",    str(len(models)))
    summary.add_row("Forecast horizon", "24 hours")
    summary.add_row("Peak vs dead",
        f"{peak_demand:.3f}x vs {dead_demand:.3f}x"
    )
    summary.add_row("Surge hours",
        str(forecast["surge_expected"].sum())
    )
    summary.add_row("Model type",       "Facebook Prophet")
    summary.add_row("Seasonality",      "daily + weekly")
    summary.add_row("Regressors",
        "is_weekend, is_friday, is_late_month"
    )
    console.print(summary)

    # Save models
    save_demand_models(models)

    console.print(
        "\n[green bold]demand.py — all checks passed. "
        "Prophet models ready.[/green bold]"
    )
