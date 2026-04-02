"""Compatibility exports for model evaluation utilities."""

from model.scoring import evaluate_two_stage, run_two_stage_evaluation
from model.train import compute_metrics

__all__ = [
    "compute_metrics",
    "evaluate_two_stage",
    "run_two_stage_evaluation",
]
