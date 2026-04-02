"""
Porter Intelligence Platform — Model Training + Evaluation

Two-stage evaluation framework:
  Stage 1: Baseline rule-based system (current Porter ops)
  Stage 2: XGBoost with confidence-weighted labels

Both evaluated on the same live_eval window.
The comparison table is the core demo deliverable.
"""

import numpy as np
import pandas as pd
import json
from pathlib import Path
from typing import Tuple, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from generator.config import (
    RANDOM_SEED, VEHICLE_TYPES, MODEL_WEIGHTS,
    PILOT_SUCCESS_CRITERIA, FALSE_POSITIVE_OPS_COST,
    ANNUAL_EXTRAP_FACTOR, CONFIDENCE_HAIRCUT, DATA_RAW,
)
from model.features import (
    build_feature_matrix, FEATURE_COLUMNS,
    compute_trip_features, compute_driver_features,
    compute_behavioural_sequence_features,
)

console = Console()
np.random.seed(RANDOM_SEED)


# ── Baseline rule-based system ────────────────────────────────

def apply_baseline_rules(
    trips_df: pd.DataFrame,
    drivers_df: pd.DataFrame,
) -> pd.Series:
    """
    Stage 1: Rule-based fraud detection.
    Represents what Porter's current ops team does manually.

    Three rules — any triggered = predicted fraud:

      Rule 1: Cash payment AND fare inflated above 2x expected
              → targets cash_extortion

      Rule 2: Distance/time ratio < 0.1 AND distance > 2km
              → targets fake_trip (driver barely moved)

      Rule 3: Driver cancellation velocity >= 3 in last hour
              → targets fake_cancellation rings

    Returns pd.Series of bool predictions (True = fraud).
    """
    # Build features needed for rules
    df = compute_trip_features(trips_df)
    df = compute_driver_features(df, drivers_df)
    df = compute_behavioural_sequence_features(df)

    predictions = pd.Series(False, index=df.index)

    # Rule 1: Cash extortion signal
    rule1 = (
        (df["payment_is_cash"] == 1)
        & (df["fare_to_expected_ratio"] > 2.0)
    )

    # Rule 2: Fake trip signal
    rule2 = (
        (df["distance_time_ratio"] < 0.10)
        & (df["declared_distance_km"] > 2.0)
    )

    # Rule 3: Cancellation ring signal
    rule3 = df["driver_cancellation_velocity_1hr"] >= 3

    predictions = rule1 | rule2 | rule3

    flagged = predictions.sum()
    console.print(
        f"[cyan]Baseline rules:[/cyan] "
        f"Rule1(cash extortion): {rule1.sum()} | "
        f"Rule2(fake trip): {rule2.sum()} | "
        f"Rule3(cancel ring): {rule3.sum()} | "
        f"Total flagged: {flagged}"
    )

    return predictions


# ── Evaluation metrics ────────────────────────────────────────

def compute_metrics(
    y_true: pd.Series,
    y_pred: pd.Series,
    recoverable_amounts: pd.Series,
    label: str = "Model",
) -> Dict:
    """
    Compute all evaluation metrics including the pilot KPIs.

    Returns dict with:
      detection metrics:  precision, recall, f1, fpr
      KPI metrics:        fraud_caught, fraud_missed,
                          recoverable_detected_inr,
                          false_alarm_cost_inr,
                          net_recoverable_inr,
                          net_recoverable_per_trip
      pilot_pass:         dict of pass/fail per criterion
    """
    from sklearn.metrics import (
        precision_score, recall_score, f1_score,
        confusion_matrix,
    )

    y_true_arr = y_true.values.astype(int)
    y_pred_arr = y_pred.values.astype(int)
    total_trips = len(y_true_arr)

    # Handle edge case — no predictions
    if y_pred_arr.sum() == 0:
        return {
            "label": label,
            "precision": 0.0, "recall": 0.0,
            "f1": 0.0, "fpr": 0.0,
            "fraud_caught": 0, "fraud_missed": int(y_true_arr.sum()),
            "false_alarms": 0,
            "recoverable_detected_inr": 0.0,
            "false_alarm_cost_inr": 0.0,
            "net_recoverable_inr": 0.0,
            "net_recoverable_per_trip": 0.0,
            "total_trips": total_trips,
            "total_fraud": int(y_true_arr.sum()),
            "pilot_pass": {
                "detection_improvement": False,
                "fpr_under_8pct": True,
                "recoverable_per_trip": False,
            },
        }

    # Detection metrics
    precision = float(precision_score(
        y_true_arr, y_pred_arr, zero_division=0,
    ))
    recall = float(recall_score(
        y_true_arr, y_pred_arr, zero_division=0,
    ))
    f1 = float(f1_score(
        y_true_arr, y_pred_arr, zero_division=0,
    ))

    tn, fp, fn, tp = confusion_matrix(
        y_true_arr, y_pred_arr, labels=[0, 1],
    ).ravel()

    fpr = float(fp / max(fp + tn, 1))

    # KPI metrics
    fraud_caught = int(tp)
    fraud_missed = int(fn)
    false_alarms = int(fp)

    # Recovered: sum recoverable_amount for correctly flagged fraud
    correct_fraud_mask = (y_true == 1) & (y_pred == 1)
    recoverable_detected = float(
        recoverable_amounts[correct_fraud_mask].sum()
    )

    # False alarm cost: ops cost per incorrect flag
    false_alarm_cost = false_alarms * FALSE_POSITIVE_OPS_COST

    net_recoverable = recoverable_detected - false_alarm_cost
    net_recoverable_per_trip = net_recoverable / max(total_trips, 1)

    return {
        "label":                    label,
        "precision":                round(precision, 4),
        "recall":                   round(recall, 4),
        "f1":                       round(f1, 4),
        "fpr":                      round(fpr, 4),
        "fraud_caught":             fraud_caught,
        "fraud_missed":             fraud_missed,
        "false_alarms":             false_alarms,
        "recoverable_detected_inr": round(recoverable_detected, 2),
        "false_alarm_cost_inr":     round(false_alarm_cost, 2),
        "net_recoverable_inr":      round(net_recoverable, 2),
        "net_recoverable_per_trip": round(net_recoverable_per_trip, 4),
        "total_trips":              total_trips,
        "total_fraud":              int(y_true_arr.sum()),
        "pilot_pass": {
            "fpr_under_8pct": fpr <= PILOT_SUCCESS_CRITERIA[
                "max_false_positive_rate"
            ],
            "recoverable_per_trip": net_recoverable_per_trip >= PILOT_SUCCESS_CRITERIA[
                "min_net_recoverable_per_trip"
            ],
        },
    }


# ── Threshold tuning ──────────────────────────────────────────

def tune_threshold(
    y_val: pd.Series,
    y_prob: np.ndarray,
    recoverable: pd.Series,
) -> float:
    """
    Find the optimal classification threshold on validation data.

    Constraint: FPR must stay <= 8% (hard ceiling from config.py)
    Objective:  Maximise net_recoverable_per_trip

    Search: 0.10 to 0.90 in 0.01 steps.
    Returns the threshold that maximises net recovery
    while keeping FPR <= 8%.
    """
    best_threshold = 0.5
    best_metric    = -np.inf

    for threshold in np.arange(0.10, 0.961, 0.01):
        y_pred = pd.Series(
            (y_prob >= threshold).astype(int),
            index=y_val.index,
        )
        metrics = compute_metrics(y_val, y_pred, recoverable)
        fpr     = metrics["fpr"]
        net_rec = metrics["net_recoverable_per_trip"]

        if fpr <= PILOT_SUCCESS_CRITERIA["max_false_positive_rate"]:
            if net_rec > best_metric:
                best_metric    = net_rec
                best_threshold = float(threshold)

    console.print(
        f"[cyan]Tuned threshold: {best_threshold:.2f} "
        f"(net recovery: ₹{best_metric:.2f}/trip)[/cyan]"
    )

    return best_threshold


# ── Training pipeline ─────────────────────────────────────────

def train_xgboost(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    weights_train: pd.Series,
) -> Tuple:
    """
    Train XGBoost fraud detection model.

    Key parameters:
      scale_pos_weight: handles class imbalance automatically
      eval_metric: aucpr (precision-recall AUC for imbalanced)
      early_stopping: prevents overfitting on validation set
      sample_weight: confidence-weighted training (Option B)

    Returns (model, feature_importance_dict)
    """
    import xgboost as xgb

    n_fraud     = int(y_train.sum())
    n_non_fraud = int((~y_train.astype(bool)).sum())
    spw         = n_non_fraud / max(n_fraud, 1)

    console.print(
        f"[dim]Training XGBoost: "
        f"{len(X_train):,} samples | "
        f"fraud: {n_fraud:,} | "
        f"scale_pos_weight: {spw:.1f}[/dim]"
    )

    model = xgb.XGBClassifier(
        n_estimators          = 500,
        max_depth             = 6,
        learning_rate         = 0.05,
        subsample             = 0.8,
        colsample_bytree      = 0.8,
        scale_pos_weight      = spw,
        eval_metric           = "aucpr",
        early_stopping_rounds = 50,
        random_state          = RANDOM_SEED,
        n_jobs                = -1,
        verbosity             = 0,
    )

    # 90/10 internal split for early stopping
    split_idx = int(len(X_train) * 0.90)
    X_tr = X_train.iloc[:split_idx]
    y_tr = y_train.iloc[:split_idx]
    w_tr = weights_train.iloc[:split_idx]
    X_es = X_train.iloc[split_idx:]
    y_es = y_train.iloc[split_idx:]

    model.fit(
        X_tr, y_tr,
        sample_weight      = w_tr,
        eval_set           = [(X_es, y_es)],
        verbose            = False,
    )

    # Feature importance
    importance = dict(zip(
        FEATURE_COLUMNS,
        model.feature_importances_.tolist(),
    ))
    top10 = sorted(
        importance.items(), key=lambda x: x[1], reverse=True,
    )[:10]

    console.print("[cyan]Top 10 feature importances:[/cyan]")
    for feat, imp in top10:
        bar = "█" * int(imp * 200)
        console.print(f"  {feat:<45} {imp:.4f} {bar}")

    # Verify moat features are in top 5
    top5_features = [f for f, _ in top10[:5]]
    moat_features = [
        "driver_cancellation_velocity_1hr",
        "fare_to_expected_ratio",
        "payment_is_cash",
    ]
    moat_in_top5 = sum(
        1 for f in moat_features if f in top5_features
    )
    if moat_in_top5 < 2:
        console.print(
            "[yellow]⚠️  Less than 2 moat features in top 5. "
            "Check fraud injection at this sample size.[/yellow]"
        )
    else:
        console.print(
            f"[green]✅ {moat_in_top5}/3 moat features in top 5 "
            f"importance[/green]"
        )

    return model, importance


# ── Main training + evaluation function ──────────────────────

def run_training_pipeline(
    trips_df:    pd.DataFrame,
    drivers_df:  pd.DataFrame,
) -> Dict:
    """
    Full training and evaluation pipeline.

    Steps:
      1. Split trips into historical and live_eval
      2. Build feature matrices for each window
      3. Run baseline rules on live_eval
      4. Train XGBoost on historical window
      5. Tune threshold on historical validation slice
      6. Evaluate XGBoost on live_eval window
      7. Print comparison table
      8. Save model weights + evaluation report
      9. Print pilot success criteria pass/fail

    Returns evaluation report dict.
    """
    console.rule("[cyan]Porter Fraud Detection — Training Pipeline[/cyan]")

    # ── Split by window ────────────────────────────────────────
    hist_df = trips_df[
        trips_df["data_split"] == "historical"
    ].reset_index(drop=True)
    eval_df = trips_df[
        trips_df["data_split"] == "live_eval"
    ].reset_index(drop=True)

    console.print(
        f"[dim]Historical: {len(hist_df):,} trips | "
        f"Live eval: {len(eval_df):,} trips[/dim]"
    )

    # ── Stage 1: Baseline on live_eval ────────────────────────
    console.rule("[yellow]Stage 1 — Baseline Rules[/yellow]")
    baseline_preds = apply_baseline_rules(eval_df, drivers_df)

    baseline_metrics = compute_metrics(
        y_true              = eval_df["is_fraud"].astype(int),
        y_pred              = baseline_preds.astype(int),
        recoverable_amounts = eval_df["recoverable_amount_inr"],
        label               = "Baseline (Rules)",
    )

    # ── Stage 2: XGBoost ──────────────────────────────────────
    console.rule("[cyan]Stage 2 — XGBoost Training[/cyan]")

    # Build historical feature matrix (training data)
    X_hist, y_hist, w_hist = build_feature_matrix(
        hist_df, drivers_df, fit_mode=True,
    )

    # 80/20 split within historical for threshold tuning
    split_idx   = int(len(X_hist) * 0.80)
    X_train     = X_hist.iloc[:split_idx]
    y_train     = y_hist.iloc[:split_idx]
    w_train     = w_hist.iloc[:split_idx]
    X_val       = X_hist.iloc[split_idx:]
    y_val       = y_hist.iloc[split_idx:]
    recov_val   = hist_df["recoverable_amount_inr"].iloc[split_idx:]

    # Train model
    model, feature_importance = train_xgboost(
        X_train, y_train, w_train,
    )

    # Tune threshold on validation slice
    y_val_prob = model.predict_proba(X_val)[:, 1]
    threshold  = tune_threshold(y_val, pd.Series(
        y_val_prob, index=X_val.index,
    ), recov_val)

    # Build live_eval feature matrix
    X_eval, y_eval, _ = build_feature_matrix(
        eval_df, drivers_df, fit_mode=True,
    )

    # Predict on live_eval
    y_eval_prob = model.predict_proba(X_eval)[:, 1]
    y_eval_pred = pd.Series(
        (y_eval_prob >= threshold).astype(int),
        index=eval_df.index,
    )

    xgb_metrics = compute_metrics(
        y_true              = eval_df["is_fraud"].astype(int),
        y_pred              = y_eval_pred,
        recoverable_amounts = eval_df["recoverable_amount_inr"],
        label               = "XGBoost",
    )

    # ── Improvement calculation ────────────────────────────────
    baseline_rec = baseline_metrics["net_recoverable_per_trip"]
    xgb_rec      = xgb_metrics["net_recoverable_per_trip"]

    improvement_pct = (
        (xgb_rec - baseline_rec) / max(abs(baseline_rec), 0.01)
    ) * 100

    xgb_metrics["pilot_pass"]["detection_improvement"] = (
        improvement_pct >= PILOT_SUCCESS_CRITERIA[
            "min_detection_improvement_pct"
        ]
    )
    baseline_metrics["pilot_pass"]["detection_improvement"] = False

    # ── Print comparison table ─────────────────────────────────
    console.rule("[green]Two-Stage Evaluation Results[/green]")

    comp = Table(
        title="Porter AI Fraud Detection — Pilot Validation Table",
        show_header=True,
        header_style="bold cyan",
    )
    comp.add_column("Metric",          style="cyan",   min_width=32)
    comp.add_column("Baseline (Rules)",justify="right", min_width=18)
    comp.add_column("XGBoost",         justify="right", min_width=18)
    comp.add_column("Delta",           justify="right", min_width=12)
    comp.add_column("Status",          justify="center",min_width=8)

    def delta_str(b, x, higher_is_better=True):
        d = x - b
        sign = "+" if d >= 0 else ""
        better = (d > 0) == higher_is_better
        color = "green" if better else "red"
        return f"[{color}]{sign}{d:.4f}[/{color}]"

    def pct_delta(b, x):
        if b == 0:
            return "[green]+inf[/green]"
        d = (x - b) / abs(b) * 100
        sign = "+" if d >= 0 else ""
        color = "green" if d >= 0 else "red"
        return f"[{color}]{sign}{d:.1f}%[/{color}]"

    m = baseline_metrics
    x = xgb_metrics

    comp.add_row(
        "Fraud cases caught",
        str(m["fraud_caught"]), str(x["fraud_caught"]),
        pct_delta(m["fraud_caught"], x["fraud_caught"]),
        "✅" if x["fraud_caught"] > m["fraud_caught"] else "❌",
    )
    comp.add_row(
        "Fraud cases missed",
        str(m["fraud_missed"]), str(x["fraud_missed"]),
        pct_delta(m["fraud_missed"], x["fraud_missed"]),
        "✅" if x["fraud_missed"] < m["fraud_missed"] else "❌",
    )
    comp.add_row(
        "False alarms",
        str(m["false_alarms"]), str(x["false_alarms"]),
        pct_delta(m["false_alarms"], x["false_alarms"]),
        "✅" if x["fpr"] <= 0.08 else "❌",
    )
    comp.add_row(
        "False positive rate",
        f"{m['fpr']*100:.2f}%", f"{x['fpr']*100:.2f}%",
        "",
        "✅" if x["fpr"] <= 0.08 else "❌",
    )
    comp.add_row(
        "Precision",
        f"{m['precision']:.4f}", f"{x['precision']:.4f}",
        delta_str(m["precision"], x["precision"]),
        "",
    )
    comp.add_row(
        "Recall",
        f"{m['recall']:.4f}", f"{x['recall']:.4f}",
        delta_str(m["recall"], x["recall"]),
        "",
    )
    comp.add_row(
        "F1 score",
        f"{m['f1']:.4f}", f"{x['f1']:.4f}",
        delta_str(m["f1"], x["f1"]),
        "",
    )
    comp.add_row("─" * 30, "─" * 16, "─" * 16, "─" * 10, "─" * 6)
    comp.add_row(
        "₹ Recoverable detected",
        f"₹{m['recoverable_detected_inr']:,.0f}",
        f"₹{x['recoverable_detected_inr']:,.0f}",
        pct_delta(
            m["recoverable_detected_inr"],
            x["recoverable_detected_inr"],
        ),
        "✅" if x["recoverable_detected_inr"] >
                m["recoverable_detected_inr"] else "❌",
    )
    comp.add_row(
        "False alarm ops cost",
        f"₹{m['false_alarm_cost_inr']:,.0f}",
        f"₹{x['false_alarm_cost_inr']:,.0f}",
        "",
        "✅" if x["false_alarm_cost_inr"] <=
                m["false_alarm_cost_inr"] else "—",
    )
    comp.add_row(
        "Net recoverable (₹)",
        f"₹{m['net_recoverable_inr']:,.0f}",
        f"₹{x['net_recoverable_inr']:,.0f}",
        pct_delta(
            m["net_recoverable_inr"],
            x["net_recoverable_inr"],
        ),
        "✅" if x["net_recoverable_inr"] >
                m["net_recoverable_inr"] else "❌",
    )
    comp.add_row(
        "Net recoverable per trip",
        f"₹{m['net_recoverable_per_trip']:.2f}",
        f"₹{x['net_recoverable_per_trip']:.2f}",
        pct_delta(
            m["net_recoverable_per_trip"],
            x["net_recoverable_per_trip"],
        ),
        "✅" if x["net_recoverable_per_trip"] >= 0.50 else "❌",
    )

    console.print(comp)

    # ── Pilot success criteria ─────────────────────────────────
    console.rule("[green]Pilot Success Criteria[/green]")

    criteria_table = Table(show_header=True)
    criteria_table.add_column("Criterion",   style="cyan", min_width=40)
    criteria_table.add_column("Target",      justify="right")
    criteria_table.add_column("Achieved",    justify="right")
    criteria_table.add_column("Result",      justify="center")

    # Criterion 1: Detection improvement
    criteria_table.add_row(
        "Detection improvement vs baseline",
        f">= {PILOT_SUCCESS_CRITERIA['min_detection_improvement_pct']:.0f}%",
        f"{improvement_pct:.1f}%",
        "✅" if xgb_metrics["pilot_pass"][
            "detection_improvement"
        ] else "❌",
    )

    # Criterion 2: False positive rate
    criteria_table.add_row(
        "False positive rate",
        f"<= {PILOT_SUCCESS_CRITERIA['max_false_positive_rate']*100:.0f}%",
        f"{x['fpr']*100:.2f}%",
        "✅" if xgb_metrics["pilot_pass"]["fpr_under_8pct"] else "❌",
    )

    # Criterion 3: Net recoverable per trip
    criteria_table.add_row(
        "Net recoverable per trip",
        f">= ₹{PILOT_SUCCESS_CRITERIA['min_net_recoverable_per_trip']:.2f}",
        f"₹{x['net_recoverable_per_trip']:.2f}",
        "✅" if xgb_metrics["pilot_pass"][
            "recoverable_per_trip"
        ] else "❌",
    )

    console.print(criteria_table)

    all_pass = all(xgb_metrics["pilot_pass"].values())
    if all_pass:
        console.print(Panel.fit(
            "[green bold]✅ ALL PILOT CRITERIA PASSED\n"
            "This system is ready for Porter's live pilot.[/green bold]",
            border_style="green",
        ))
    else:
        console.print(Panel.fit(
            "[yellow]⚠️  Some criteria need attention.\n"
            "Review the table above.[/yellow]",
            border_style="yellow",
        ))

    # ── Annual extrapolation ───────────────────────────────────
    annual_rec = (
        x["net_recoverable_per_trip"]
        * 98_000_000   # Porter's estimated annual trips
        * CONFIDENCE_HAIRCUT
    )
    your_royalty = annual_rec * 0.04

    console.print("\n[cyan]Annual extrapolation (conservative):[/cyan]")
    console.print(
        f"  Net recoverable/year: "
        f"[green]₹{annual_rec/1e7:.1f} crore[/green]"
    )
    console.print(
        f"  Your 4% royalty/year: "
        f"[green]₹{your_royalty/1e7:.1f} crore[/green]"
    )

    # ── Save artifacts ─────────────────────────────────────────
    MODEL_WEIGHTS.mkdir(parents=True, exist_ok=True)

    # Save model
    model_path = MODEL_WEIGHTS / "xgb_fraud_model.json"
    model.save_model(str(model_path))

    # Save feature names
    feat_path = MODEL_WEIGHTS / "feature_names.json"
    with open(feat_path, "w") as f:
        json.dump(FEATURE_COLUMNS, f)

    # Save threshold
    thresh_path = MODEL_WEIGHTS / "threshold.json"
    with open(thresh_path, "w") as f:
        json.dump({"threshold": threshold}, f)

    # Save full evaluation report
    report = {
        "baseline":           baseline_metrics,
        "xgboost":            xgb_metrics,
        "improvement_pct":    round(improvement_pct, 2),
        "threshold_used":     threshold,
        "feature_importance": feature_importance,
        "annual_extrapolation": {
            "net_recoverable_crore": round(annual_rec / 1e7, 2),
            "royalty_at_4pct_crore": round(your_royalty / 1e7, 2),
        },
        "pilot_ready":        all_pass,
    }

    report_path = DATA_RAW / "evaluation_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    console.print(f"\n[green]✅ Model saved → {model_path}[/green]")
    console.print(f"[green]✅ Report saved → {report_path}[/green]")

    return report


# ── Entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    import pandas as pd

    console.rule(
        "[cyan]Porter Intelligence Platform — Training[/cyan]"
    )

    # Prefer full-scale data on disk; fall back to generated sample
    trips_path   = DATA_RAW / "trips_full_fraud.csv"
    drivers_path = DATA_RAW / "drivers_full.csv"

    if trips_path.exists() and drivers_path.exists():
        console.print(
            f"[cyan]Loading full-scale data from disk...[/cyan]"
        )
        trips_df   = pd.read_csv(trips_path)
        drivers_df = pd.read_csv(drivers_path)
        console.print(
            f"[dim]{len(trips_df):,} trips, "
            f"{len(drivers_df):,} drivers[/dim]"
        )
    else:
        from generator.drivers import generate_drivers
        from generator.customers import generate_customers
        from generator.trips import generate_trips
        from generator.fraud import inject_fraud

        console.print(
            "[dim]No full-scale data found. Generating "
            "(5K drivers, 5K customers, 20K trips)...[/dim]"
        )
        drivers_df   = generate_drivers(
            n=5000, city_filter="bangalore",
        )
        customers_df = generate_customers(
            n=5000, city_filter="bangalore",
        )
        trips_df = generate_trips(
            drivers_df, customers_df,
            n=20_000, city_filter="bangalore",
        )
        trips_df = inject_fraud(trips_df, drivers_df)

    report = run_training_pipeline(trips_df, drivers_df)

    console.print(
        "\n[green bold]✅ Training complete.[/green bold]"
    )
