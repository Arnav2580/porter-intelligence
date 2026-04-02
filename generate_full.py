"""
Porter Intelligence Platform — Full Scale Generator

Generates 500K trips, 50K drivers, 100K customers
and retrains all models. Run once before deployment.

Runtime on Mac Mini M4: ~20-25 minutes total.
Close all other applications before running.
Memory usage peaks at ~8GB during trip generation.

Usage:
  python generate_full.py
"""

import time
import json
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from generator.config import (
    RANDOM_SEED, NUM_DRIVERS, NUM_CUSTOMERS,
    NUM_TRIPS, DATA_RAW, MODEL_WEIGHTS
)

console   = Console()
t_start   = time.time()


def section(n: int, total: int, label: str):
    elapsed = int(time.time() - t_start)
    console.rule(
        f"[cyan]Step {n}/{total} — {label} "
        f"[dim]({elapsed//60}m {elapsed%60}s elapsed)"
        f"[/dim][/cyan]"
    )


def main() -> bool:

    console.print(Panel.fit(
        "[bold cyan]Porter Intelligence Platform[/bold cyan]\n"
        "[dim]Full Scale Data Generation + Retrain[/dim]\n"
        f"\n[dim]Drivers:   {NUM_DRIVERS:,}[/dim]\n"
        f"[dim]Customers: {NUM_CUSTOMERS:,}[/dim]\n"
        f"[dim]Trips:     {NUM_TRIPS:,}[/dim]",
        border_style="cyan"
    ))

    # ══════════════════════════════════════════════
    # STEP 1 — Drivers
    # ══════════════════════════════════════════════
    section(1, 6, "Generating driver profiles")
    from generator.drivers import generate_drivers

    drivers_df = generate_drivers(n=NUM_DRIVERS)
    drivers_df.to_csv(DATA_RAW / "drivers_full.csv", index=False)

    ring_members = (
        int(drivers_df["fraud_ring_id"].notna().sum())
        if "fraud_ring_id" in drivers_df.columns
        else 0
    )
    n_rings = (
        int(drivers_df["fraud_ring_id"].nunique()) - 1
        if "fraud_ring_id" in drivers_df.columns
        else 0
    )

    console.print(
        f"[green]✅ {len(drivers_df):,} drivers[/green]  "
        f"[dim]{ring_members} ring members "
        f"across {n_rings} rings[/dim]"
    )

    # ══════════════════════════════════════════════
    # STEP 2 — Customers
    # ══════════════════════════════════════════════
    section(2, 6, "Generating customer profiles")
    from generator.customers import generate_customers

    customers_df = generate_customers(n=NUM_CUSTOMERS)
    customers_df.to_csv(
        DATA_RAW / "customers_full.csv", index=False
    )
    console.print(
        f"[green]✅ {len(customers_df):,} customers[/green]"
    )

    # ══════════════════════════════════════════════
    # STEP 3 — Trips
    # ══════════════════════════════════════════════
    section(3, 6, "Generating trip records (~10 min)")
    from generator.trips import generate_trips

    trips_df = generate_trips(
        drivers_df,
        customers_df,
        n=NUM_TRIPS,
        city_filter=None,    # all 7 cities
    )
    trips_df.to_csv(DATA_RAW / "trips_full.csv", index=False)

    hist = int((trips_df["data_split"] == "historical").sum())
    evl  = int((trips_df["data_split"] == "live_eval").sum())
    console.print(
        f"[green]✅ {len(trips_df):,} trips[/green]  "
        f"[dim]Historical: {hist:,} | Live eval: {evl:,}[/dim]"
    )

    # ══════════════════════════════════════════════
    # STEP 4 — Fraud injection
    # ══════════════════════════════════════════════
    section(4, 6, "Injecting fraud patterns")
    from generator.fraud import inject_fraud

    trips_fraud = inject_fraud(trips_df, drivers_df)
    trips_fraud.to_csv(
        DATA_RAW / "trips_full_fraud.csv", index=False
    )

    n_fraud    = int(trips_fraud["is_fraud"].sum())
    fraud_rate = n_fraud / len(trips_fraud) * 100
    n_ring_coord = (
        int(trips_fraud["ring_coordination"].sum())
        if "ring_coordination" in trips_fraud.columns
        else 0
    )

    console.print(
        f"[green]✅ {n_fraud:,} fraud cases "
        f"({fraud_rate:.2f}%)[/green]  "
        f"[dim]{n_ring_coord} ring coordination events[/dim]"
    )

    # Check RING_NEW_001 emergence at full scale
    if "ring_coordination" in trips_fraud.columns:
        live_ring = trips_fraud[
            (trips_fraud["data_split"] == "live_eval")
            & (trips_fraud["ring_coordination"] == True)
        ]
        if len(live_ring) > 0:
            console.print(
                f"[green]✅ RING_NEW_001: "
                f"{len(live_ring)} events in live_eval "
                f"window[/green]"
            )
        else:
            console.print(
                "[yellow]⚠️  RING_NEW_001 not visible "
                "at this scale — acceptable[/yellow]"
            )

    # Validate fraud rate before training
    if not (3.0 <= fraud_rate <= 9.0):
        console.print(
            f"[red]❌ Fraud rate {fraud_rate:.2f}% "
            f"outside expected 3-9%[/red]"
        )
        console.print(
            "[red]Check fraud injection before "
            "proceeding.[/red]"
        )
        return False

    # ══════════════════════════════════════════════
    # STEP 5 — XGBoost fraud model
    # ══════════════════════════════════════════════
    section(5, 6, "Training XGBoost fraud model")
    from model.train import run_training_pipeline

    report   = run_training_pipeline(trips_fraud, drivers_df)
    xgb      = report.get("xgboost", {})
    baseline = report.get("baseline", {})

    # Print comparison table
    t = Table(title="Full Scale Model Results")
    t.add_column("Metric",    style="cyan")
    t.add_column("Baseline",  justify="right")
    t.add_column("XGBoost",   justify="right", style="green")
    t.add_column("Status",    justify="center")

    t.add_row(
        "Fraud caught",
        str(baseline.get("fraud_caught", 0)),
        str(xgb.get("fraud_caught", 0)),
        "✅" if xgb.get("fraud_caught", 0)
              > baseline.get("fraud_caught", 0)
        else "❌"
    )
    t.add_row(
        "False positive rate",
        f"{baseline.get('fpr', 0)*100:.2f}%",
        f"{xgb.get('fpr', 0)*100:.2f}%",
        "✅" if xgb.get("fpr", 0) <= 0.08 else "❌"
    )
    t.add_row(
        "Net rec / trip",
        f"₹{baseline.get('net_recoverable_per_trip', 0):.2f}",
        f"₹{xgb.get('net_recoverable_per_trip', 0):.2f}",
        "✅" if xgb.get(
            "net_recoverable_per_trip", 0
        ) >= 0.50 else "❌"
    )
    t.add_row(
        "Improvement vs baseline",
        "—",
        f"+{report.get('improvement_pct', 0):.1f}%",
        "✅" if report.get("improvement_pct", 0) >= 25
        else "❌"
    )
    console.print(t)

    # Hard stop if pilot criteria fail
    pilot_pass = xgb.get("pilot_pass", {})
    if not all(pilot_pass.values()):
        console.print(Panel.fit(
            "[red bold]❌ PILOT CRITERIA FAILED "
            "AT FULL SCALE[/red bold]\n\n"
            "[red]Do not deploy until resolved.\n"
            "Most likely cause: threshold needs retuning\n"
            "Check model/train.py tune_threshold()[/red]",
            border_style="red"
        ))
        return False

    console.print(
        "[green bold]✅ All 3 pilot criteria pass "
        "at full scale[/green bold]"
    )

    # Print annual extrapolation
    annual = report.get("annual_extrapolation", {})
    console.print(
        f"[cyan]Annual recovery: "
        f"₹{annual.get('net_recoverable_crore', 0):.1f} Cr  "
        f"Your royalty: "
        f"₹{annual.get('royalty_at_4pct_crore', 0):.1f} Cr[/cyan]"
    )

    # ══════════════════════════════════════════════
    # STEP 6 — Prophet demand models
    # ══════════════════════════════════════════════
    section(6, 6, "Training Prophet demand models")
    from model.demand import (
        train_demand_models, save_demand_models
    )

    demand_models = train_demand_models(trips_fraud)
    save_demand_models(demand_models)

    console.print(
        f"[green]✅ {len(demand_models)} Prophet models "
        f"trained and saved[/green]"
    )

    # ══════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════
    runtime = int(time.time() - t_start)

    summary = Table(title="Day 11 — Full Scale Complete")
    summary.add_column("Component",  style="cyan")
    summary.add_column("Result",     style="green")
    summary.add_column("Status",     justify="center")

    summary.add_row(
        "Driver profiles",
        f"{len(drivers_df):,}", "✅"
    )
    summary.add_row(
        "Customer profiles",
        f"{len(customers_df):,}", "✅"
    )
    summary.add_row(
        "Trip records total",
        f"{len(trips_fraud):,}", "✅"
    )
    summary.add_row(
        "Fraud cases",
        f"{n_fraud:,}  ({fraud_rate:.2f}%)", "✅"
    )
    summary.add_row(
        "Prophet demand models",
        str(len(demand_models)), "✅"
    )
    summary.add_row(
        "XGBoost pilot criteria",
        "3/3 passing", "✅"
    )
    summary.add_row(
        "Annual recovery estimate",
        f"₹{annual.get('net_recoverable_crore', 0):.1f} Cr",
        "✅"
    )
    summary.add_row(
        "Runtime",
        f"{runtime//60}m {runtime%60}s", "—"
    )
    console.print(summary)

    console.print(Panel.fit(
        "[green bold]Full scale generation complete.[/green bold]\n\n"
        "[dim]Next steps:\n"
        "1. Restart the API:\n"
        "   uvicorn api.main:app --port 8000\n\n"
        "2. Verify it loaded full scale data:\n"
        "   curl http://localhost:8000/health\n"
        "   (should show trips_loaded >> 10,000)\n\n"
        "3. Run generate.py --test to confirm\n"
        "   21/21 still passing.[/dim]",
        border_style="green"
    ))

    return True


if __name__ == "__main__":
    ok = main()
    if not ok:
        exit(1)
