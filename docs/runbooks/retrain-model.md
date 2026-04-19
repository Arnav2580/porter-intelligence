# Runbook - Retrain The Fraud Model

[Runbooks](./README.md)

Objective:
- regenerate fraud model artifacts and refreshed evaluation outputs

## Steps

1. Activate the virtual environment.
2. Confirm dependencies are installed.
3. Run the training pipeline.
4. Validate updated artifacts and evaluation report.
5. Restart the API and confirm `/health`.

## Commands

```bash
source venv/bin/activate
PYTHONPATH=$(pwd) python model/train.py
PYTHONPATH=$(pwd) python model/scoring.py
PYTHONPATH=$(pwd) ./venv/bin/pytest tests/test_model.py -q
```

## Artifacts To Check

- `model/weights/xgb_fraud_model.json`
- `model/weights/feature_names.json`
- `model/weights/two_stage_config.json`
- `data/raw/evaluation_report.json`

## Acceptance Check

- KPI math reconciles
- action threshold remains intentional
- reviewed-case and evaluation docs still match the artifact names surfaced in the API
