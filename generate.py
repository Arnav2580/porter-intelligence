#!/usr/bin/env python3
"""
Porter Intelligence Platform — Main Data Generation Entry Point
Usage: python generate.py --city bangalore --trips 100000
       python generate.py --test
"""

import click
import numpy as np
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from generator.config import (
    CITIES, VEHICLE_TYPES, FRAUD_TYPES,
    FRAUD_BASE_RATE, HISTORICAL_DAYS, LIVE_EVAL_DAYS,
    NUM_DRIVERS, NUM_CUSTOMERS,
)
from generator.cities import ZONES, CITY_ZONES

console = Console()


@click.command()
@click.option("--city",  default="bangalore", help="City to generate data for")
@click.option("--trips", default=100_000,     help="Number of trips to generate")
@click.option("--test",  is_flag=True,        help="Run validation test only")
def main(city: str, trips: int, test: bool) -> None:
    """Porter Intelligence Platform — Data Generator"""

    if test:
        run_test_validation()
        return

    console.print(Panel.fit(
        "[bold cyan]Porter Intelligence Platform[/bold cyan]\n"
        "[dim]Digital Twin Generator — Full Run[/dim]",
        border_style="cyan",
    ))
    console.print(f"[yellow]City:[/yellow]  {city.title()}")
    console.print(f"[yellow]Trips:[/yellow] {trips:,}")
    console.print(
        "\n[dim]Drivers and Customers modules not yet "
        "implemented — run after Day 2.[/dim]"
    )


def run_test_validation() -> None:
    """Validate project structure and Days 1–2 modules."""
    console.print(Panel.fit(
        "[bold green]Porter Intelligence Platform[/bold green]\n"
        "[dim]Day 2 — Structure + Generator Validation[/dim]",
        border_style="green",
    ))

    results: list[tuple[str, str, str]] = []

    # Test 1: Config imports
    try:
        from generator.config import (
            VEHICLE_TYPES, FRAUD_TYPES, PILOT_SUCCESS_CRITERIA,
            WEEKDAY_HOUR_WEIGHTS,
        )
        assert abs(sum(WEEKDAY_HOUR_WEIGHTS) - 1.0) < 0.0001
        results.append(("generator/config.py", "✅",
                         f"{len(VEHICLE_TYPES)} vehicles, "
                         f"{len(FRAUD_TYPES)} fraud types"))
    except Exception as e:
        results.append(("generator/config.py", "❌", str(e)))

    # Test 2: Cities imports
    try:
        from generator.cities import (
            ZONES, CITY_ZONES,
            get_random_point_in_zone,
            get_road_distance_km,
            get_zone_demand_pattern,
        )
        blr_count = len(CITY_ZONES.get("bangalore", []))
        results.append(("generator/cities.py", "✅",
                         f"{len(ZONES)} zones, "
                         f"{blr_count} in Bangalore"))
    except Exception as e:
        results.append(("generator/cities.py", "❌", str(e)))

    # Test 3: Drivers module functional
    try:
        from generator.drivers import generate_drivers
        sample_drivers = generate_drivers(n=100, city_filter="bangalore")
        assert len(sample_drivers) == 100
        assert "fraud_propensity" in sample_drivers.columns
        assert sample_drivers["fraud_propensity"].between(0, 1).all()
        results.append((
            "generator/drivers.py", "✅",
            f"100 drivers, fraud_propensity range "
            f"[{sample_drivers['fraud_propensity'].min():.3f}, "
            f"{sample_drivers['fraud_propensity'].max():.3f}]",
        ))
    except Exception as e:
        results.append(("generator/drivers.py", "❌", str(e)))

    # Test 4: Customers module functional
    try:
        from generator.customers import generate_customers
        sample_customers = generate_customers(n=100, city_filter="bangalore")
        assert len(sample_customers) == 100
        assert "business_type" in sample_customers.columns
        biz_types_found = sample_customers["business_type"].nunique()
        results.append((
            "generator/customers.py", "✅",
            f"100 customers, {biz_types_found} business types found",
        ))
    except Exception as e:
        results.append(("generator/customers.py", "❌", str(e)))

    # Test 5: Trips module importable and split logic correct
    try:
        from generator.trips import (
            build_date_windows,
            calculate_fare,
            calculate_duration,
            assign_trip_status,
            is_night_trip,
        )

        h_start, h_end, e_start, e_end = build_date_windows()
        assert h_start < h_end < e_start < e_end, \
            "Date windows out of order"

        test_fare = calculate_fare(
            "mini_truck", 10.0, 1.5, False,
            np.random.default_rng(42),
        )
        assert test_fare >= 200, \
            f"Mini truck fare ₹{test_fare:.0f} below base ₹200"

        from datetime import datetime as _dt
        night_dt = _dt(2024, 1, 15, 23, 30, 0)
        day_dt   = _dt(2024, 1, 15, 14, 0, 0)
        assert is_night_trip(night_dt),     "23:30 should be night"
        assert not is_night_trip(day_dt),   "14:00 should not be night"

        results.append((
            "generator/trips.py", "✅",
            f"Date windows OK | Fare ₹{test_fare:.0f} | "
            f"Night detection OK",
        ))
    except Exception as e:
        results.append(("generator/trips.py", "❌", str(e)))

    # Test 6: Fraud module importable and functions correct
    try:
        from generator.fraud import (
            get_temporal_fraud_multiplier,
            sample_confidence_score,
            FRAUD_APPLIERS,
        )

        # Temporal: Friday must have higher multiplier than Monday
        fri_mult = get_temporal_fraud_multiplier(
            "2024-01-05 20:00:00", "historical"  # Friday
        )
        mon_mult = get_temporal_fraud_multiplier(
            "2024-01-08 10:00:00", "historical"  # Monday
        )
        assert fri_mult > mon_mult, \
            "Friday multiplier must exceed Monday"

        # live_eval must exceed historical for same day
        hist_mult = get_temporal_fraud_multiplier(
            "2024-01-05 20:00:00", "historical"
        )
        eval_mult = get_temporal_fraud_multiplier(
            "2024-01-05 20:00:00", "live_eval"
        )
        assert eval_mult > hist_mult, \
            "live_eval multiplier must exceed historical"

        # All 6 fraud types have appliers
        assert len(FRAUD_APPLIERS) == 6, \
            "Must have applier for all 6 fraud types"

        # Confidence scores in valid range
        test_rng = np.random.default_rng(42)
        for ftype in FRAUD_APPLIERS:
            score = sample_confidence_score(ftype, test_rng)
            assert 0.5 <= score <= 1.0, \
                f"Confidence out of range for {ftype}: {score}"

        results.append((
            "generator/fraud.py", "✅",
            f"Temporal multipliers OK | "
            f"Fri:{fri_mult:.2f} Mon:{mon_mult:.2f} | "
            f"6 fraud types with appliers"
        ))
    except Exception as e:
        results.append(("generator/fraud.py", "❌", str(e)))

    # Test 7: Features module
    try:
        from model.features import (
            build_feature_matrix, FEATURE_COLUMNS,
            compute_trip_features,
        )
        assert len(FEATURE_COLUMNS) >= 25, \
            "Must have at least 25 features"
        results.append((
            "model/features.py",
            "✅",
            f"{len(FEATURE_COLUMNS)} features defined",
        ))
    except Exception as e:
        results.append(("model/features.py", "❌", str(e)))

    # Test 8: Train module importable
    try:
        from model.train import (
            apply_baseline_rules,
            compute_metrics,
            tune_threshold,
        )
        results.append((
            "model/train.py",
            "✅",
            "Baseline, metrics, threshold tuner ready",
        ))
    except Exception as e:
        results.append(("model/train.py", "❌", str(e)))

    # Test 9: Masking module functional
    try:
        from masking.pseudonymise import hash_id, verify_masking_quality
        test_hash = hash_id("test_driver_001")
        assert len(test_hash) == 16, "Hash must be 16 chars"
        assert hash_id("test") == hash_id("test"), \
            "Hash must be deterministic"
        results.append((
            "masking/pseudonymise.py",
            "✅",
            f"hash_id working: test→{test_hash}"
        ))
    except Exception as e:
        results.append(("masking/pseudonymise.py", "❌", str(e)))

    # Test 10: API module importable
    try:
        from api.schemas import (
            TripScoreRequest, TripScoreResponse,
            KPISummaryResponse,
        )
        from api.main import app
        results.append((
            "api/main.py",
            "✅",
            "FastAPI app + all schemas importable"
        ))
    except Exception as e:
        results.append(("api/main.py", "❌", str(e)))

    # Test 11: Compatibility modules importable
    compatibility_modules = [
        "model.evaluate",  "model.kpi",
    ]
    for mod in compatibility_modules:
        try:
            __import__(mod)
            results.append((mod, "✅", "compatibility exports ready"))
        except Exception as e:
            results.append((mod, "❌", str(e)))

    # Test 12: Demand model module functional
    try:
        from model.demand import (
            prepare_demand_series,
            train_demand_models,
            forecast_zone,
            load_demand_models,
        )
        models = load_demand_models()
        if models:
            detail = f"{len(models)} trained models on disk"
        else:
            detail = "importable, no models on disk yet"
        results.append(("model/demand.py", "✅", detail))
    except Exception as e:
        results.append(("model/demand.py", "❌", str(e)))

    # Test 13: Query engine module functional
    try:
        from model.query import (
            answer_query,
            build_structured_answer,
            load_context,
        )
        ctx = load_context()
        test_result = answer_query("Give me the KPI summary")
        assert test_result["source"] in ("structured", "llm"), \
            "Query must return structured or llm source"
        assert len(test_result["answer"]) > 20, \
            "Answer must be non-trivial"
        results.append((
            "model/query.py", "✅",
            f"KPI query OK | {test_result['response_ms']}ms | "
            f"source={test_result['source']}"
        ))
    except Exception as e:
        results.append(("model/query.py", "❌", str(e)))

    # Test 14: Query router importable
    try:
        from api.routes.query import router as query_router
        results.append((
            "api/routes/query.py", "✅",
            "POST /query router ready"
        ))
    except Exception as e:
        results.append(("api/routes/query.py", "❌", str(e)))

    # Test 15: Driver intelligence module functional
    try:
        from model.driver_intelligence import (
            get_driver_intelligence,
            compute_risk_timeline,
            compute_peer_comparison,
            compute_ring_intelligence,
            generate_recommendation,
        )
        results.append((
            "model/driver_intelligence.py", "✅",
            "5 functions importable"
        ))
    except Exception as e:
        results.append(("model/driver_intelligence.py", "❌", str(e)))

    # Test 16: Driver intelligence router importable
    try:
        from api.routes.driver_intelligence import (
            router as intelligence_router,
        )
        results.append((
            "api/routes/driver_intelligence.py", "✅",
            "GET /intelligence/* routes ready"
        ))
    except Exception as e:
        results.append((
            "api/routes/driver_intelligence.py", "❌", str(e)
        ))

    # Test 17: Route efficiency module functional
    try:
        from model.route_efficiency import (
            compute_dead_mile_rate,
            compute_hourly_utilisation,
            generate_reallocation_suggestions,
            compute_fleet_summary,
            run_route_efficiency,
        )
        results.append((
            "model/route_efficiency.py",
            "✅",
            "Route efficiency engine ready"
        ))
    except Exception as e:
        results.append((
            "model/route_efficiency.py", "❌", str(e)
        ))

    # Test 18: Route efficiency routes importable
    try:
        from api.routes.route_efficiency import router
        results.append((
            "api/routes/route_efficiency.py",
            "✅",
            "/efficiency/summary + /reallocation "
            "+ /dead-miles + /utilisation/{zone}"
        ))
    except Exception as e:
        results.append((
            "api/routes/route_efficiency.py",
            "❌", str(e)
        ))

    # Test 19: Full scale generator importable
    try:
        import generate_full
        results.append((
            "generate_full.py",
            "✅",
            "Ready — run python generate_full.py"
        ))
    except Exception as e:
        results.append(("generate_full.py", "❌", str(e)))

    # Test 20: Data scale verification
    try:
        from generator.config import DATA_RAW
        full_path  = DATA_RAW / "trips_full_fraud.csv"
        small_path = DATA_RAW / "trips_with_fraud_10k.csv"

        if full_path.exists():
            row_count = sum(
                1 for _ in open(full_path)
            ) - 1  # subtract header
            results.append((
                "Data scale",
                "✅",
                f"Full scale: ~{row_count:,} trips"
            ))
        elif small_path.exists():
            results.append((
                "Data scale",
                "⚠️",
                "10K sample only — "
                "run python generate_full.py before demo"
            ))
        else:
            results.append((
                "Data scale",
                "❌",
                "No trip data found"
            ))
    except Exception as e:
        results.append(("Data scale", "❌", str(e)))

    # Print results table
    table = Table(title="Day 11 — Validation Report")
    table.add_column("Module",  style="cyan", min_width=30)
    table.add_column("Status",  justify="center")
    table.add_column("Detail",  style="dim")
    for module, status, detail in results:
        table.add_row(module, status, detail)
    console.print(table)

    # Summary
    passed = sum(1 for _, s, _ in results if s == "✅")
    warns  = sum(1 for _, s, _ in results if s == "⚠️")
    total  = len(results)

    if passed + warns == total and warns == 0:
        console.print(
            f"\n[green]{passed}/{total} checks passed[/green]"
        )
        console.print(
            "[green bold]✅ 21/21 checks passed. "
            "Run python generate_full.py "
            "then proceed to Day 12 deployment."
            "[/green bold]"
        )
    elif passed + warns == total and warns > 0:
        console.print(
            f"\n[yellow]{passed} passed, {warns} warnings[/yellow]"
        )
        console.print(
            f"[yellow]⚠️  {passed} passed, {warns} warnings. "
            f"Run python generate_full.py to resolve.[/yellow]"
        )
    else:
        fails = total - passed - warns
        console.print(
            f"\n[red]{passed} passed, {warns} warnings, "
            f"{fails} failed[/red]"
        )


if __name__ == "__main__":
    main()
